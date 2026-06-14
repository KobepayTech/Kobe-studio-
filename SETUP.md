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

## 5. Hardware gate / coin-device trigger

In admin, set:

```text
Hardware gate required = true
Hardware gate key = your-secret-device-key
Gate amount = 1
```

The booth will wait after style selection until the trigger arrives.

Hardware controller POST example:

```http
POST /api/hardware/trigger
Content-Type: application/json

{"key":"your-secret-device-key","session_id":"SESSION_ID","amount":"1"}
```

If `session_id` is omitted, the backend unlocks the latest waiting session.

## 6. Printing

Browser print is available on the result page.

Server print is available in admin session cards.

Auto-print can be enabled in admin:

```text
Auto print completed photos = true
Print enabled = true
```

On Windows, server print uses the default printer configured in Windows.

## 7. Logo upload

Open admin, upload a logo image in the Logo Upload panel. The booth and admin header will use it immediately.

## 8. Connect Stable Diffusion and choose models

Install and run Automatic1111 with API enabled:

```bash
webui-user.bat --api --xformers
```

In admin:

1. Confirm the Stable Diffusion API URL.
2. Click Load Available Models.
3. Copy/select a model name.
4. Choose style: anime, comic, watercolor, etc.
5. Save model to style.

This writes the selected model directly into `checkpoints.json`.

## 9. Windows packaging

Build the Windows app folder:

```bash
build_windows.bat
```

Output:

```text
dist\KobeStudio\
```

To create a proper installer, install Inno Setup and compile:

```text
packaging\kobe_studio.iss
```

## 10. Backend storage

The app creates `kobe_studio.db` automatically. It stores:

- settings
- guests
- sessions
- status and progress
- result paths
- QR paths
- hardware gate state
- print state

## 11. Remaining polish tasks

- Add advanced printer selection using pywin32 for exact printer routing.
- Add real hardware firmware examples for ESP32/Arduino.
- Add theme background upload.
- Add signed admin users instead of one password.
