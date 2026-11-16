@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --onefile --windowed --name "Vydacha_Vytyah" vydacha_vytyah.py
echo.
echo Готовий файл: dist\Vydacha_Vytyah.exe
echo Папку data поруч із EXE зберігайте разом із програмою.
pause
