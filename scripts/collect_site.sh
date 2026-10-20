#!/usr/bin/env bash
# 公開するファイルだけを _site に集める（ページを公開するワークフローがすべてこれを使う）。
# 確認リスト（data/check.md）、設定・手順書・スクリプト、保管しているデザイン案（_bk）は公開しない。
# 公開するファイルを増やすときは、ここに書き足す。
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf _site
mkdir -p _site/data
cp index.html index_zine.html _site/
cp data/genres.js data/covers_manual.js data/covers_auto.js data/display.js _site/data/
echo "公開するファイル：$(find _site -type f | wc -l)件"
