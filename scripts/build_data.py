"""「ジャンルから探す」の作品データを、kintoneから毎月作り直す。

読むアプリ（すべて読み取りだけ。kintoneには何も書き込まない）
  402 連載情報   … 書名・著者・ジャンル表記・内容紹介・連載ステータス・PV累計・出版実績URL・特殊（連載分類）
  507 連載分類   … 大分類・小分類（主）
  341 記事       … 記事ID・カテゴリコード・回数・公開日時（第1回の記事と、491をつなぐため）
  491 単日PV     … 記事ごとの単日SNPV（直近3か月の並び順）

書き出すファイル
  data/genres.js       作品データ（ページが読む）
  data/covers_auto.js  新しい連載の書影（追記のみ。確定済みの covers_manual.js には触らない）
  data/check.md        人が確認するリスト（書影が取れなかった作品など）

公開リポジトリでは実行ログを誰でも見られるため、ログには件数だけを出し、
書名などの中身は出さない。
"""
import calendar
import datetime as dt
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
JST = dt.timezone(dt.timedelta(hours=9))
DOMAIN = os.environ.get("KINTONE_DOMAIN", "").strip().replace("https://", "").rstrip("/")
UA = "Mozilla/5.0 (compatible; genreMapping-monthly/1.0)"


# ---------------------------------------------------------------- kintone
def kintone(method, path, token, params=None, body=None):
    url = f"https://{DOMAIN}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {"X-Cybozu-API-Token": token}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.load(res)
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            if e.code >= 500 and attempt < 2:
                time.sleep(3)
                continue
            raise SystemExit(f"！ kintoneの読み込みに失敗しました（{path} HTTP {e.code}）：{msg}")
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(3)
                continue
            raise


def fetch_all(app, fields, query=""):
    """カーソルAPIで全件を読む（指定した項目だけ）。"""
    token = os.environ.get(f"KINTONE_TOKEN_{app}", "").strip()
    if not token:
        raise SystemExit(f"！ シークレット KINTONE_TOKEN_{app} が登録されていません")
    cur = kintone("POST", "/k/v1/records/cursor.json", token,
                  body={"app": app, "fields": fields, "query": query, "size": 500})
    rows = []
    try:
        while True:
            j = kintone("GET", "/k/v1/records/cursor.json", token, params={"id": cur["id"]})
            for r in j["records"]:
                rows.append({k: (v.get("value") if isinstance(v, dict) else v) for k, v in r.items()})
            if not j.get("next"):
                break
    except BaseException:
        try:
            kintone("DELETE", "/k/v1/records/cursor.json", token, body={"id": cur["id"]})
        except BaseException:
            pass
        raise
    print(f"アプリ{app}：{len(rows)}件を読み込みました")
    return rows


# ---------------------------------------------------------------- 文字の整え
def nfkc(s):
    return unicodedata.normalize("NFKC", str(s or "")).strip()


PICKUP_WORDS = re.compile(r"ピックアップ|集中|再掲|再連載|一挙|特集|一気読み|番外")


def base_title(t):
    """ピックアップ版などの印（［］【】や（〜ピックアップ）など）を外した書名。"""
    s = nfkc(t)
    s = re.sub(r"[\[［【〔].*?[\]］】〕]", "", s)
    s = re.sub(r"[(（]([^)）]*)[)）]", lambda m: "" if PICKUP_WORDS.search(m.group(1)) else m.group(0), s)
    return re.sub(r"\s+", " ", s).strip()


def title_key(t):
    return re.sub(r"[\s・「」『』〜~～\-―—:：、。,.!?！？]", "", base_title(t)).lower()


def to_int(v):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def digits(v):
    m = re.search(r"\d+", str(v or ""))
    return m.group(0) if m else ""


def ymd(v):
    """「2026-07-01」「2026/7/1」「2026-07-01T00:00:00Z」などを日付にする。"""
    m = re.match(r"\s*(\d{4})\D(\d{1,2})\D(\d{1,2})", str(v or ""))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ---------------------------------------------------------------- 期間
def recent_period(today):
    """実行した月の前月までの3か月（例：10月に実行 → 7/1〜9/30）。"""
    y, m = today.year, today.month
    end_y, end_m = (y, m - 1) if m > 1 else (y - 1, 12)
    st_y, st_m = end_y, end_m - 2
    while st_m <= 0:
        st_m += 12
        st_y -= 1
    start = dt.date(st_y, st_m, 1)
    end = dt.date(end_y, end_m, calendar.monthrange(end_y, end_m)[1])
    label = f"{st_y}年{st_m}月〜{end_m}月" if st_y == end_y else f"{st_y}年{st_m}月〜{end_y}年{end_m}月"
    return start, end, label


# ---------------------------------------------------------------- ファイル
def read_js_object(path, var):
    if not os.path.exists(path):
        return {}
    s = open(path, encoding="utf-8").read()
    m = re.search(r"window\." + var + r"\s*=\s*(\{.*\})\s*;\s*$", s, re.S)
    return json.loads(m.group(1)) if m else {}


def write_js(path, var, obj, comment):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"/* {comment} */\nwindow.{var} = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n")


# ---------------------------------------------------------------- 書影
def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", "replace")


IMG_RE = re.compile(r'<img[^>]*class="[^"]*m-book-info__img[^"]*"[^>]*>', re.I)
SRC_RE = re.compile(r'src="([^"]+)"')
HASH_RE = re.compile(r"mwimgs/([0-9a-f])/([0-9a-f])/\d+\w*/img_([0-9a-f]+\.(?:jpg|jpeg|png|gif|webp))", re.I)


def cover_from_article(f):
    """第1回の記事の書籍情報欄。本が1冊だけのときだけ採用する。"""
    try:
        page = http_get(f"https://renaissance-media.jp/articles/-/{f}")
    except Exception:
        return None, "記事を読めない"
    imgs = []
    for tag in IMG_RE.findall(page):
        m = SRC_RE.search(tag)
        if m and m.group(1) not in imgs:
            imgs.append(m.group(1))
    if len(imgs) == 1:
        h = HASH_RE.search(imgs[0])
        return (h.group(3) if h else imgs[0]), "記事の書籍情報欄"
    return None, ("書籍情報欄に本が複数" if imgs else "書籍情報欄が無い")


def cover_from_product(url):
    """出版実績URL（幻冬舎ルネッサンスの本のページ）の og:image。"""
    if not url or "gentosha-book.com/products/" not in url:
        return None
    try:
        page = http_get(url)
    except Exception:
        return None
    m = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    return html.unescape(m.group(1)) if m else None


# ---------------------------------------------------------------- 本体
def main():
    if not DOMAIN:
        raise SystemExit("！ シークレット KINTONE_DOMAIN が登録されていません")
    today = dt.datetime.now(JST).date()
    r_start, r_end, r_label = recent_period(today)
    config = json.load(open(os.path.join(ROOT, "genres_config.json"), encoding="utf-8"))
    sub2genre, subname2code = {}, {}
    for g in config:
        for s in g["subs"]:
            sub2genre[s["code"]] = g["id"]
            subname2code[nfkc(s["name"])] = s["code"]

    # ---- 読み込み
    r402 = fetch_all("402", ["カテゴリID", "書籍タイトル", "著者名", "メインジャンル", "内容紹介", "連載ステータス",
                             "SNPV", "GLOPV", "特殊", "出版実績URL"])
    r507 = fetch_all("507", ["作品キー", "大分類", "小分類_主"])
    # 341・491は項目の型の違いで絞り込み条件が通らないことがないよう、全件を読んでからこちらで絞る
    r341 = fetch_all("341", ["記事ID", "カテゴリコード", "回数・数値", "公開日時"])
    r491 = fetch_all("491", ["article_id", "article_view", "date"])
    now_utc = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    r341 = [r for r in r341 if not r.get("公開日時") or str(r["公開日時"])[:19] <= now_utc]
    r491 = [r for r in r491 if r_start <= (ymd(r.get("date")) or dt.date.min) <= r_end]

    # ---- 507：連載コード → 小分類コード（企画・その他など、設定に無い小分類は対象外）
    cls, unknown_sub = {}, 0
    for r in r507:
        key = nfkc(r.get("作品キー"))
        v = nfkc(r.get("小分類_主"))
        m = re.match(r"(S\d{2})", v)
        code = m.group(1) if m else subname2code.get(v) or next((c for n, c in subname2code.items() if n and n in v), None)
        if key and code in sub2genre:
            cls[key] = code
        elif key:
            unknown_sub += 1
    print(f"分類：{len(cls)}件を使います（対象外の小分類 {unknown_sub}件）")

    # ---- 341：連載コード → 第1回の記事、記事ID → 連載コード
    art2cat, first = {}, {}
    for r in r341:
        c, a = nfkc(r.get("カテゴリコード")), digits(r.get("記事ID"))
        if not c or not a:
            continue
        art2cat[a] = c
        n = r.get("回数・数値")
        n = to_int(n) if n not in (None, "") else 10 ** 6
        t = r.get("公開日時") or "9999"
        if c not in first or (n, t) < first[c][:2]:
            first[c] = (n, t, a)

    # ---- 491：直近3か月のSNPVを連載コードごとに合計
    recent = {}
    for r in r491:
        c = art2cat.get(digits(r.get("article_id")))
        if c:
            recent[c] = recent.get(c, 0) + to_int(r.get("article_view"))
    print(f"直近3か月（{r_label}）：{len(recent)}連載に単日PVがありました")

    # ---- 402：同じ作品（ピックアップ版など）をまとめる
    groups = {}
    for r in r402:
        c = nfkc(r.get("カテゴリID"))
        if not c or not nfkc(r.get("書籍タイトル")):
            continue
        r["_c"] = c
        r["_pv"] = to_int(r.get("SNPV")) + to_int(r.get("GLOPV"))
        r["_pr"] = recent.get(c, 0)
        groups.setdefault(title_key(r.get("書籍タイトル")), []).append(r)

    works_by_sub = {}
    stats = {"402": len(r402), "作品": 0, "分類なし": 0, "まとめた登録": 0}
    special_values = {}
    for key, rs in groups.items():
        for r in rs:
            sv = nfkc(r.get("特殊")) or "（空）"
            special_values[sv] = special_values.get(sv, 0) + 1
        cand = [r for r in rs if r["_c"] in cls]
        if not cand:
            stats["分類なし"] += 1
            continue
        normal = [r for r in cand if "通常" in nfkc(r.get("特殊"))]
        rep = max(normal or cand, key=lambda r: r["_pv"])
        f = first.get(rep["_c"]) or next((first[r["_c"]] for r in sorted(rs, key=lambda r: -r["_pv"]) if r["_c"] in first), None)
        w = {
            "t": base_title(rep.get("書籍タイトル")) if rep not in normal else nfkc(rep.get("書籍タイトル")),
            "a": nfkc(rep.get("著者名")),
            "g": nfkc(rep.get("メインジャンル")),
            "s": nfkc(rep.get("内容紹介")),
            "c": rep["_c"],
            "f": f[2] if f else "",
            "l": 1 if "連載中" in nfkc(rep.get("連載ステータス")) else 0,
            "pv": max(r["_pv"] for r in rs),
            "pr": max(r["_pr"] for r in rs),
            "_url": next((nfkc(r.get("出版実績URL")) for r in [rep] + rs if nfkc(r.get("出版実績URL"))), ""),
        }
        works_by_sub.setdefault(cls[rep["_c"]], []).append(w)
        stats["作品"] += 1
        stats["まとめた登録"] += len(rs) - 1

    # ---- 安全確認：作品数が前回より大きく減っていたら止める（kintone側の不具合などで空のページにしないため）
    prev = read_js_object(os.path.join(DATA, "genres.js"), "GLO_DATA")
    prev_n = sum(len(s["works"]) for g in prev.get("genres", []) for s in g["subs"])
    if prev_n and stats["作品"] < prev_n * 0.8:
        raise SystemExit(f"！ 作品数が前回（{prev_n}）から大きく減った（{stats['作品']}）ため、更新を止めました。kintoneの状態を確認してください。")

    # ---- 書影：確定済みにも自動にも無い連載だけ集める
    manual = read_js_object(os.path.join(DATA, "covers_manual.js"), "COVERS_MANUAL")
    auto = read_js_object(os.path.join(DATA, "covers_auto.js"), "COVERS_AUTO")
    check_cover = []
    got = {"記事の書籍情報欄": 0, "出版実績URL": 0, "取れず": 0}
    url_filled = 0
    for ws in works_by_sub.values():
        for w in ws:
            url_filled += 1 if w["_url"] else 0
            if w["c"] in manual or w["c"] in auto:
                continue
            img, why = (None, "第1回の記事が無い")
            if w["f"]:
                img, why = cover_from_article(w["f"])
                time.sleep(0.5)
            if img:
                auto[w["c"]] = img
                got["記事の書籍情報欄"] += 1
                continue
            img = cover_from_product(w["_url"])
            time.sleep(0.5)
            if img:
                auto[w["c"]] = img
                got["出版実績URL"] += 1
                check_cover.append((w, f"{why}のため、出版実績URLの書影を使いました（念のため確認）"))
            else:
                got["取れず"] += 1
                check_cover.append((w, f"{why}。出版実績URLからも取れませんでした" if w["_url"] else f"{why}。出版実績URLも未入力です"))
    print(f"書影：新しく {got['記事の書籍情報欄'] + got['出版実績URL']}件（記事 {got['記事の書籍情報欄']}／出版実績 {got['出版実績URL']}）、取れず {got['取れず']}件")

    # ---- PVの実数は公開しない：並び順だけが分かる「順位の点数」に置き換える（大きいほど上）
    all_w = [w for ws in works_by_sub.values() for w in ws]
    n = len(all_w)
    for key in ("pv", "pr"):
        order = sorted((w for w in all_w if w[key] > 0), key=lambda w: -w[key])
        score, prev_v = n, None
        for i, w in enumerate(order):
            if w[key] != prev_v:
                score, prev_v = n - i, w[key]
            w["_" + key] = score
        for w in all_w:
            w[key] = w.pop("_" + key, 0)

    # ---- 書き出し
    genres = []
    for g in config:
        subs = []
        for s in g["subs"]:
            ws = sorted(works_by_sub.get(s["code"], []), key=lambda w: -w["pv"])
            for w in ws:
                w.pop("_url", None)
            if ws:
                subs.append({"code": s["code"], "name": s["name"], "works": ws})
        if subs:
            genres.append({"id": g["id"], "name": g["name"], "desc": g["desc"], "hue": g["hue"],
                           "count": sum(len(s["works"]) for s in subs), "subs": subs})
    data = {"updated": today.isoformat(), "hasRecent": bool(recent), "recentLabel": r_label, "genres": genres}
    write_js(os.path.join(DATA, "genres.js"), "GLO_DATA", data, "作品データ（毎月自動で作り直す。手で直さない）")
    write_js(os.path.join(DATA, "covers_auto.js"), "COVERS_AUTO", auto, "新しい連載の書影（毎月の自動処理が追記する）")

    lines = [f"# 確認リスト（{today.isoformat()} 更新）", "",
             "毎月の自動更新で、人が確認したほうがよいものをまとめています。", "",
             "## 件数", "",
             f"- 作品数：{stats['作品']}（ピックアップ版などをまとめた登録 {stats['まとめた登録']}件）",
             f"- 402にあって分類が無い・対象外の作品：{stats['分類なし']}",
             f"- 直近3か月の期間：{r_label}（単日PVがあった連載 {len(recent)}）",
             f"- 出版実績URLが入っている作品：{url_filled} / {stats['作品']}",
             f"- 書影（新しく集めた分）：記事 {got['記事の書籍情報欄']}件／出版実績 {got['出版実績URL']}件／取れず {got['取れず']}件", "",
             "## 「特殊（連載分類）」の値と件数", ""]
    lines += [f"- {k}：{v}" for k, v in sorted(special_values.items(), key=lambda x: -x[1])]
    lines += ["", "## 書影の確認が必要な作品", ""]
    if check_cover:
        lines += ["| 作品名 | 著者 | 連載コード | 状況 |", "|---|---|---|---|"]
        lines += [f"| [{w['t']}](https://renaissance-media.jp/category/{w['c']}) | {w['a']} | {w['c']} | {why} |" for w, why in check_cover]
    else:
        lines.append("ありません。")
    lines += ["", "書影を直すときは `data/covers_manual.js` に「連載コード: 画像ファイル名またはURL」を書き足してください（自動の結果より優先されます）。", ""]
    with open(os.path.join(DATA, "check.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"作品データを書き出しました：{stats['作品']}作品／{len(genres)}ジャンル")


if __name__ == "__main__":
    main()
