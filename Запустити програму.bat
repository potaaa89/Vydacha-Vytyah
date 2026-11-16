@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -m pip install -r requirements.txt
py vydacha_vytyah.py
pause
