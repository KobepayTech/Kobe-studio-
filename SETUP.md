# Kobe Studio Functional Setup Checklist

## 1. Run without AI first

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000/main_page
```

Test this flow first:

1. Allow camera permission.
2. Take a photo.
3. Choose Original / No AI.
4. Confirm that the result page opens.
5. Confirm that the result image appears.
6. Confirm that QR code appears.
7. Open `/admin_data` and check that the session appears.

## 2. Connect Stable Diffusion

Install and run Automatic1111 with API enabled:

```bash
webui-user.bat --api --xformers
```

Then edit `checkpoints.json` and replace:

```text
put_your_model_here
```

with the exact checkpoint name shown in Automatic1111.

## 3. Public sharing

For event use, run Cloudflare Tunnel or use the same Wi-Fi LAN URL.

The app reads `tunnel_url.txt` when it exists. Put your public tunnel URL there, for example:

```text
https://example.trycloudflare.com
```

## 4. Next development tasks

- Build full admin gallery UI using `/admin_data`.
- Add proper admin login on the backend.
- Add event branding: logo, theme color, event name.
- Add guest phone number/email collection if needed.
- Add print support.
- Add queue/progress screen for slow AI generation.
- Package for Windows with one-click installer.
