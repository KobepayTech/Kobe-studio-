@echo off
title Kobe Studio AI Photobooth

echo Starting Kobe Studio...
echo Make sure Automatic1111 is running with --api if you want AI styles.
timeout /t 2 >nul

python app.py
pause
