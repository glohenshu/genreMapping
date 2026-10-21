# ジャンル一覧（genreMapping）

GLOの連載を、ジャンル → テーマ → 作品の地図と一覧で探せるページです。GitHub Pages で公開しています。

デザインは雑誌の目次型で確定し、`index.html`（https://glohenshu.github.io/genreMapping/ ）が本筋です。以前のURL `index_zine.html` を開くと、このページへ移ります。ほかのデザイン案（最初の版・1E・1G・1G2）は `_bk/` に保管しており、今後は更新しません（サイトには公開していません）。

## デザインの方針（決まったこと）

- 見た目は、最初に決めた雑誌の目次型（`index_zine.html` を本筋にしたときの形）をそのまま使い、崩さない。
- 読みやすさとオフィシャル感を優先した、シンプルな案にする。
- AIらしさが強い見た目や、文字が小さい見た目にはしない。
- テーマ名（小分類の名前）に括弧書きがあるとき（例：「社会問題（少子化・格差・地域の課題など）」）、括弧の中はページには出さない。
- テーマ（小分類）の名前は 2026-10 に見直した（S01〜S89 のうち31件。コードは変えていない）。名前を変えるときは、`genres_config.json`・kintone 507 の「小分類（主）」「小分類（副）」の選択肢と既存レコード・kintone 513 の小分類名・分類スキルの小分類一覧を、すべてそろえる。
- 「犬」「猫」は1つにまとめず、別々の小分類のままにする。
- ヘッダーとフッターは置かない（2026-10-21 に外した）。
- 検索欄は見出しの下（目次の上）に置き、ふだんはたたんでおく（「作品を検索する ＋」で開く）。このページに載っている作品から探す（作品名・著者名・内容紹介・ジャンル名）。GLO の記事全体の検索へ進む道は置かない。

## GLO の記事に埋め込む

GLO の記事（記事の本文の HTML）には、次のコードを貼ります。iframe の高さがページの中身に合わせて変わり、ジャンルを移ったときは記事がそのジャンルの頭までスクロールします。作品のカード・ジャンル一覧（☰）・「↑」のボタンも、いま見えている範囲に出ます。

- パソコンでは、GLO の記事の本文の幅（696px）がいちばん広い幅です。
- `<script>` が消されてしまう場合は、高さが 1600px のままになり、長いジャンルは下が切れます。そのときは知らせてください。
- 中身の高さに合わせるので、`height:clamp(...)` のような決め打ちの高さは要りません。

```html
<div style="width:100%; max-width:720px; margin:0 auto;">
<iframe id="gloGenreFrame" src="https://glohenshu.github.io/genreMapping/" title="ジャンル一覧" loading="lazy" scrolling="no" style="width:100%; border:0; display:block; height:1600px;"></iframe>
</div>
<script>
/* ジャンル一覧の埋め込み：高さを中身に合わせる・画面の移動で記事をスクロールする・見えている範囲を知らせる */
(function () {
  var ORIGIN = 'https://glohenshu.github.io';
  var TOP_SPACE = 80; // スクロールしたとき、GLO のヘッダーに隠れないように空ける高さ
  var f = document.getElementById('gloGenreFrame');
  function sendView() {
    var r = f.getBoundingClientRect();
    var top = Math.max(0, -r.top);
    var bottom = Math.min(r.height, window.innerHeight - r.top);
    if (bottom <= top) return;
    f.contentWindow.postMessage({ glo: 'genre', view: { top: top, height: bottom - top } }, ORIGIN);
  }
  window.addEventListener('message', function (e) {
    if (e.origin !== ORIGIN || e.source !== f.contentWindow || !e.data || e.data.glo !== 'genre') return;
    var d = e.data;
    if (d.height) f.style.height = d.height + 'px';
    if (typeof d.scrollTo === 'number') {
      var y = f.getBoundingClientRect().top + window.pageYOffset + d.scrollTo - TOP_SPACE;
      window.scrollTo({ top: Math.max(0, y), behavior: d.smooth ? 'smooth' : 'auto' });
    }
    sendView();
  });
  window.addEventListener('scroll', sendView, { passive: true });
  window.addEventListener('resize', sendView);
})();
</script>
```

## 毎月の自動更新

毎月5日 9:00（日本時間）に「毎月の作品データ更新」が動き、kintone（402・507・341・491 と、小分類の表示設定）を読んで次のファイルを作り直し、ページを公開し直します。kintoneへの書き込みは行いません。

| ファイル | 中身 | 手で直すか |
|---|---|---|
| `data/genres.js` | 作品データ（並び順は順位の点数。PVの実数は載せない） | 直さない（毎月上書き） |
| `data/covers_manual.js` | 確認済みの書影 | 直してよい（自動処理は触らない） |
| `data/covers_auto.js` | 新しい連載の書影（自動で追記） | 基本は直さない |
| `data/check.md` | 人が確認するリスト | 読むだけ |

手動で動かすときは「Actions」→「毎月の作品データ更新」→「Run workflow」。

## 毎月の分類作業

新しい連載は、kintone 507 で分類されるまでページに載りません。毎月1日〜4日に分類を済ませてください。手順は [docs/classification.md](docs/classification.md) にあります。

## 小分類の表示・非表示

ページに出したくない小分類は、kintone のアプリ513「小分類の表示設定」で「表示しない」にし、「Actions」→「小分類の表示設定を反映」→「Run workflow」で反映します（1分ほど。作品データには触らない）。手順は [docs/display-setting.md](docs/display-setting.md) にあります。

| ファイル | 中身 | 手で直すか |
|---|---|---|
| `data/display.js` | 表示しない小分類の一覧 | 直さない（表示設定の反映・毎月の更新で上書き） |

## ルール

- 1作品は、507 の小分類（主）と小分類（副）の両方に並ぶ。ジャンルの作品数・「全○作品」は、同じ作品を2回数えない。読者には主・副の区別を見せない。
- 同じ作品のピックアップ版などは書名でまとめ、表示は「通常」の登録を使う。並び順はまとめた中でいちばん多い値。
- 直近3か月は、実行した月の前月までの3か月（491の単日SNPV）。
- 新しい連載の書影：第1回の記事の書籍情報欄に本が1冊だけ → その書影／複数・無し → 出版実績URLの書影／どちらも無理 → `check.md` に出す。
- 書影を直すときは `data/covers_manual.js` に `"連載コード":"画像ファイル名またはURL"` を書き足す（自動の結果より優先。`""` は「書影なしで確定」）。
- 連載準備中で第1回がまだ公開されていない作品は、載せない（公開された月の更新から載る）。
- 作品数が前回より2割以上減ったときは、更新を止める。

## 公開するファイル

ページとして公開するのは、`scripts/collect_site.sh` で集めたファイルだけです（`index.html`・`index_zine.html`・`data/` の作品データ4つ）。確認リスト（`data/check.md`）、設定・手順書・スクリプト、`_bk/` の旧案は、サイトの URL からは見えません。ただしリポジトリは公開なので、GitHub 上では誰でも読めます。公開するファイルを増やすときは `scripts/collect_site.sh` に書き足してください。

## 注意

公開リポジトリのため、実行ログには件数だけを出します。トークンは Settings → Secrets にだけ置き、ファイルには書かないでください。
