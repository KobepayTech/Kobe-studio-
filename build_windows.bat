@echo off
title Build Kobe Studio for Windows

echo Creating build environment...
python -m venv .venv-build
call .venv-build\Scripts\activate

echo Installing runtime and build dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-build.txt

echo Building Kobe Studio executable with PyInstaller...
pyinstaller packaging\kobe_studio.spec --clean --noconfirm

echo.
echo Build complete. Check the dist\KobeStudio folder.
pause
