@echo off
rem Monthly classification up to the point of importing into kintone app 507.
chcp 65001 >nul
cd /d "%~dp0"
python -X utf8 scripts\monthly_classify.py %*
echo.
pause
