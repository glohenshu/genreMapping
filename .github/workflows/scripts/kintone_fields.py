"""kintoneのアプリ402・507・491について、項目（フィールド）の一覧だけを出力する。

・レコードの中身（書名・著者・担当者など）は一切出力しない。
  公開リポジトリでは Actions の実行ログを誰でも見られるため。
・出力するのは「項目コード／項目名／項目の種類」と、アプリのレコード件数だけ。
・アプリ管理権限の無いトークンでは項目名が取れないため、その場合は
  レコード1件から「項目コードと種類」だけを取り出す（値は捨てる）。
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

DOMAIN = os.environ.get("KINTONE_DOMAIN", "").strip().replace("https://", "").rstrip("/")
APPS = [("402", "連載情報・PV累計"), ("507", "連載分類"), ("491", "単日PV")]


def get(path, params, token):
    url = f"https://{DOMAIN}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"X-Cybozu-API-Token": token})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def show_app(app, name):
    token = os.environ.get(f"KINTONE_TOKEN_{app}", "").strip()
    print(f"\n==================== アプリ{app}（{name}） ====================")
    if not token:
        print(f"！ シークレット KINTONE_TOKEN_{app} が登録されていません")
        return False

    # レコード件数（中身は取らない）
    try:
        j = get("/k/v1/records.json", {"app": app, "fields[0]": "$id", "totalCount": "true", "query": "limit 1"}, token)
        print(f"レコード件数：{j.get('totalCount')}")
    except urllib.error.HTTPError as e:
        print(f"！ レコード件数を取得できません（HTTP {e.code}）：{e.read().decode('utf-8', 'replace')[:200]}")
        return False

    rows = []
    # 1) 項目名つきの一覧（アプリ管理権限があるトークンのとき）
    try:
        j = get("/k/v1/app/form/fields.json", {"app": app}, token)
        for code, p in j["properties"].items():
            rows.append((code, p.get("label", ""), p.get("type", "")))
        print("取得方法：フォーム設定（項目名あり）")
    except urllib.error.HTTPError:
        # 2) レコード1件から項目コードと種類だけ（値は使わない）
        j = get("/k/v1/records.json", {"app": app, "query": "limit 1"}, token)
        if j.get("records"):
            for code, v in j["records"][0].items():
                rows.append((code, "（項目名は取得できません）", v.get("type", "")))
        print("取得方法：レコードの項目コード（アプリ管理権限が無いため項目名なし）")

    skip = {"__ID__", "__REVISION__", "RECORD_NUMBER", "CREATOR", "CREATED_TIME", "MODIFIER", "UPDATED_TIME", "STATUS", "STATUS_ASSIGNEE", "CATEGORY"}
    print("項目コード\t項目名\t種類")
    for code, label, typ in sorted(rows, key=lambda r: r[0]):
        if typ in skip:
            continue
        print(f"{code}\t{label}\t{typ}")
    return True


def main():
    if not DOMAIN:
        print("！ シークレット KINTONE_DOMAIN が登録されていません（例：xxxx.cybozu.com）")
        sys.exit(1)
    ok = all([show_app(a, n) for a, n in APPS])
    print("\n完了しました。上の項目一覧をコピーしてClaudeに貼ってください。")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
