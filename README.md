# Kobe Studio

Kobe Studio is an AI photo booth and event studio platform for events, weddings, malls, schools, and brand activations.

It is based on the SnapPocket open-source AI photobooth workflow:

- Camera capture in the browser
- AI style transformation using Stable Diffusion / Automatic1111 img2img API
- QR download page for guests
- Admin gallery for monitoring generated images
- Local LAN access with optional Cloudflare Tunnel

## Quick Start

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

Admin:

```text
http://127.0.0.1:5000/admin
```

Default admin password:

```text
admin
```

## Stable Diffusion Setup

Run Automatic1111 with API enabled:

```bash
webui-user.bat --api --xformers
```

The default API endpoint is:

```text
http://127.0.0.1:7860/sdapi/v1/img2img
```

Edit `checkpoints.json` and replace `put_your_model_here` with your installed Stable Diffusion checkpoint name.

## Project Structure

```text
app.py
checkpoints.json
requirements.txt
run.bat
templates/
  index.html
  download.html
  admin.html
static/
  preview/
  qr/
public/
temp/
```

## Source Attribution

Kobe Studio is based on concepts and workflow from SnapPocket by moveNb3at / SnapPocket Dev Team.

Original project: https://github.com/movenb3at/snap-pocket

## License

SnapPocket is AGPL-3.0. Kobe Studio keeps AGPL-3.0 attribution and source-sharing requirements.
