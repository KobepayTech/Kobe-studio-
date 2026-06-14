@echo off
title Kobe Studio AI Photobooth

echo Starting Kobe Studio...
echo Local booth: http://127.0.0.1:5000/main_page
echo Admin: http://127.0.0.1:5000/admin
echo Default admin password is set by KOBE_ADMIN_PASSWORD or fallback admin.
echo Make sure Automatic1111 is running with --api if you want AI styles.
timeout /t 2 >nul

python app.py
pause
