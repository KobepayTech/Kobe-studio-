# Kobe Studio Functional Setup Checklist

## 1. Run without AI first

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open on the same computer:

```text
http://127.0.0.1:5000/main_page
```

Test this flow first:

1. Allow camera permission.
2. Confirm the back camera starts by default on iPhone.
3. Use Switch Camera to change front/back.
4. Take a photo.
5. Choose Original / No AI.
6. Confirm that the result page opens.
7. Confirm that the result image appears.
8. Confirm that QR code appears.
9. Open `/admin_data` and check that the session appears.

## 2. iPhone camera testing

For iPhone Safari, the camera works best when the app is opened using HTTPS.

Use one of these:

- Cloudflare Tunnel public HTTPS URL.
- A proper HTTPS domain.
- Localhost only if testing on the same device.

The app now requests the back camera first using `facingMode: environment`, falls back to the front camera if needed, and includes a Switch Camera button.

## 3. Connect Stable Diffusion

Install and run Automatic1111 with API enabled:

```bash
webui-user.bat --api --xformers
```

Then edit `checkpoints.json` and replace:

```text
put_your_model_here
```

with the exact checkpoint name shown in Automatic1111.

## 4. Public sharing

For event use, run Cloudflare Tunnel or use the same Wi-Fi LAN URL.

The app reads `tunnel_url.txt` when it exists. Put your public tunnel URL there, for example:

```text
https://example.trycloudflare.com
```

## 5. Next development tasks

- Build full admin gallery UI using `/admin_data`.
- Add proper admin login on the backend.
- Add event branding: logo, theme color, event name.
- Add guest phone number/email collection if needed.
- Add print support.
- Add queue/progress screen for slow AI generation.
- Package for Windows with one-click installer.
