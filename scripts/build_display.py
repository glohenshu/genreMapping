"""小分類の表示設定だけを反映する（作品データには触らない）。

読むアプリ：小分類の表示設定（シークレット KINTONE_DISPLAY_APP のアプリ）だけ。kintoneには何も書き込まない。
書き出すファイル：data/display.js（表示しない小分類の一覧。ページはこれを見て、その小分類を隠す）
"""
import build_data as bd


def main():
    if not bd.DOMAIN:
        raise SystemExit("！ シークレット KINTONE_DOMAIN が登録されていません")
    if not bd.DISPLAY_APP:
        raise SystemExit("！ シークレット KINTONE_DISPLAY_APP が登録されていません")
    bd.write_display(bd.read_hidden())


if __name__ == "__main__":
    main()
