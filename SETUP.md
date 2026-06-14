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

Admin:

```text
http://127.0.0.1:5000/admin
```

Default admin password is `admin`. For real use, set `KOBE_ADMIN_PASSWORD` before starting the app.

## 2. Run backend smoke test

After installing requirements, run:

```bash
python tests\smoke_test.py
```

This tests upload, queued transform, status polling, final result, and result page loading.

## 3. Manual booth test

1. Allow camera permission.
2. Confirm the back camera starts by default on iPhone.
3. Use Switch Camera to change front/back.
4. Take a photo.
5. Optionally enter guest name/contact.
6. Choose Original / No AI.
7. Confirm progress polling moves from queued to completed.
8. Confirm that the result page opens.
9. Confirm that the result image appears.
10. Confirm that QR code appears.
11. Confirm that Print Photo works on the result page.
12. Open `/admin` and check that the session appears in the gallery.

## 4. iPhone camera testing

For iPhone Safari, the camera works best when the app is opened using HTTPS.

Use:

```bash
run_public.bat
```

This starts the Flask app and Cloudflare Tunnel helper. When a `trycloudflare.com` URL appears, the helper saves it into `tunnel_url.txt` so QR links use the public HTTPS URL.

The app requests the back camera first using `facingMode: environment`, falls back to the front camera if needed, and includes a Switch Camera button.

## 5. Connect Stable Diffusion

Install and run Automatic1111 with API enabled:

```bash
webui-user.bat --api --xformers
```

Then edit `checkpoints.json` and replace:

```text
put_your_model_here
```

with the exact checkpoint name shown in Automatic1111.

You can also update the Stable Diffusion API URL from the admin settings page.

## 6. Admin dashboard

The admin dashboard now includes:

- Event name
- Brand color
- Stable Diffusion API URL
- Public tunnel URL
- Printer name field
- Print enabled switch
- Session gallery
- Result links
- Delete session action

## 7. Backend storage

The app creates `kobe_studio.db` automatically. It stores:

- settings
- guests
- sessions
- status and progress
- result paths
- QR paths

## 8. Remaining polish tasks

- Add physical printer integration for automatic printing.
- Add real payment or coin trigger hardware.
- Add theme/logo upload.
- Add model picker UI that writes selected model into `checkpoints.json`.
- Package as Windows installer.
