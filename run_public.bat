@echo off
title Kobe Studio Public HTTPS

echo Starting Kobe Studio Flask server...
start "Kobe Studio Flask" cmd /k "python app.py"

timeout /t 4 >nul

echo Starting Cloudflare Tunnel and saving public URL...
python tools\cloudflare_tunnel.py
pause
