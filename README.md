# Kobe Studio

Kobe Studio is an AI photo booth and event studio platform for events, weddings, malls, schools, and brand activations.

It is based on the SnapPocket open-source AI photobooth workflow and now includes a functional production-MVP backend.

## Current Features

- Browser camera capture with iPhone back camera default
- Switch Camera button for front/back camera
- Optional guest name/contact record
- SQLite database for sessions, guests, and settings
- Queued image processing with progress polling
- Stable Diffusion / Automatic1111 img2img API support
- Local fallback filters when AI model is not configured
- QR result page
- Printable result page
- Server-side print action from admin
- Optional auto-print on completed sessions
- Hardware gate trigger API for coin/cash/payment devices
- Logo upload from admin
- Model picker that writes selected model names into `checkpoints.json`
- Admin login
- Admin dashboard with event settings and session gallery
- Cloudflare Tunnel helper for iPhone HTTPS testing
- Windows build script and installer script

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open booth:

```text
http://127.0.0.1:5000/main_page
```

Open admin:

```text
http://127.0.0.1:5000/admin
```

Default admin password:

```text
admin
```

Change it before real use:

```bash
set KOBE_ADMIN_PASSWORD=your-new-password
python app.py
```

## Public iPhone Testing

For iPhone camera access, use HTTPS. The simplest helper is:

```bash
run_public.bat
```

This starts the Flask app and Cloudflare Tunnel. The helper writes the public URL into `tunnel_url.txt`, and the backend uses that for QR links.

## Stable Diffusion Setup

Run Automatic1111 with API enabled:

```bash
webui-user.bat --api --xformers
```

Default API endpoint:

```text
http://127.0.0.1:7860/sdapi/v1/img2img
```

In the admin dashboard, click **Load Available Models**, copy a model name, choose a style, and save it. This updates `checkpoints.json`.

If no real model name is configured, Kobe Studio falls back to local filters/original image so the booth can still run.

## Hardware Gate Trigger

Enable **Hardware gate required** in admin settings.

Your hardware controller can unlock the latest waiting session by sending:

```http
POST /api/hardware/trigger
Content-Type: application/json

{"key":"change-this-key","amount":"1"}
```

Or unlock a specific session:

```json
{"key":"change-this-key","session_id":"SESSION_ID","amount":"1"}
```

## Printing

- Browser print: available on the result page.
- Server print: available in admin session cards.
- Auto-print: enable `auto_print_on_complete` in admin settings.

On Windows, server print uses the Windows default printer. Set the default printer in Windows settings before running events.

## Windows Build

Build the app folder:

```bash
build_windows.bat
```

This creates:

```text
dist/KobeStudio/
```

To create an installer, install Inno Setup and compile:

```text
packaging/kobe_studio.iss
```

## Project Structure

```text
app.py
checkpoints.json
requirements.txt
requirements-build.txt
run.bat
run_public.bat
build_windows.bat
tools/cloudflare_tunnel.py
packaging/kobe_studio.spec
packaging/kobe_studio.iss
templates/
  index.html
  login.html
  download.html
  admin.html
uploads/
static/
  preview/
  qr/
public/
temp/
```

## Important Runtime Files

These are generated locally and ignored by Git:

```text
kobe_studio.db
tunnel_url.txt
public/*
temp/*
static/qr/*
uploads/*
```

## Source Attribution

Kobe Studio is based on concepts and workflow from SnapPocket by moveNb3at / SnapPocket Dev Team.

Original project: https://github.com/movenb3at/snap-pocket

## License

SnapPocket is AGPL-3.0. Kobe Studio keeps AGPL-3.0 attribution and source-sharing requirements.
