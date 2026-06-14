from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import shutil
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import qrcode
import requests
from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
PUBLIC_DIR = BASE_DIR / "public"
PREVIEW_DIR = BASE_DIR / "static" / "preview"
QR_DIR = BASE_DIR / "static" / "qr"

for folder in (TEMP_DIR, PUBLIC_DIR, PREVIEW_DIR, QR_DIR):
    folder.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("kobe-studio")

app = Flask(__name__)
SD_URL = os.getenv("KOBE_SD_URL", "http://127.0.0.1:7860/sdapi/v1/img2img")
ADMIN_PASSWORD = os.getenv("KOBE_ADMIN_PASSWORD", "admin")


def get_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


def get_base_url() -> str:
    tunnel_file = BASE_DIR / "tunnel_url.txt"
    if tunnel_file.exists():
        try:
            value = tunnel_file.read_text(encoding="utf-8").strip()
            if value:
                return value.rstrip("/")
        except UnicodeDecodeError:
            value = tunnel_file.read_text(encoding="utf-16", errors="ignore").strip()
            if value:
                return value.rstrip("/")
    return f"http://{get_lan_ip()}:5000"


def read_style_config() -> dict[str, Any]:
    config_file = BASE_DIR / "checkpoints.json"
    with config_file.open("r", encoding="utf-8") as handle:
        return json.load(handle).get("checkpoints", {})


def image_to_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def save_data_url(data_url: str, path: Path) -> None:
    if "," not in data_url:
        raise ValueError("Invalid image data URL")
    raw = data_url.split(",", 1)[1]
    path.write_bytes(base64.b64decode(raw))


def local_filter(raw_path: Path, style_key: str) -> str:
    image = Image.open(raw_path).convert("RGB")
    if style_key == "distortion_lens_filter":
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        rows, cols = img_cv.shape[:2]
        mapy, mapx = np.indices((rows, cols), dtype=np.float32)
        mapx = 2 * mapx / (cols - 1) - 1
        mapy = 2 * mapy / (rows - 1) - 1
        radius, theta = cv2.cartToPolar(mapx, mapy)
        radius[radius < 1] = radius[radius < 1] ** 2
        mapx, mapy = cv2.polarToCart(radius, theta)
        mapx = ((mapx + 1) * cols - 1) / 2
        mapy = ((mapy + 1) * rows - 1) / 2
        result = cv2.remap(img_cv, mapx, mapy, cv2.INTER_LINEAR)
        ok, buffer = cv2.imencode(".png", result)
        if not ok:
            raise RuntimeError("OpenCV distortion filter failed")
        return base64.b64encode(buffer).decode("utf-8")

    if style_key == "canny_filter":
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(img_cv, 50, 150)
        rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
        ok, buffer = cv2.imencode(".png", rgb)
        if not ok:
            raise RuntimeError("OpenCV canny filter failed")
        return base64.b64encode(buffer).decode("utf-8")

    return base64.b64encode(raw_path.read_bytes()).decode("utf-8")


def stable_diffusion_transform(raw_path: Path, style_key: str, gender: str | None) -> str:
    styles = read_style_config()
    cfg = dict(styles.get(style_key, {}))

    if not cfg.get("model_name") or cfg.get("model_name") == "put_your_model_here":
        return local_filter(raw_path, style_key)

    image = Image.open(raw_path).convert("RGB")
    width, height = image.size
    init_b64 = base64.b64encode(raw_path.read_bytes()).decode("utf-8")

    prompt = cfg.get("prompt", "")
    negative_prompt = cfg.get("negative_prompt", "")
    if gender == "male":
        prompt = f"handsome man, {prompt}"
    elif gender == "female":
        prompt = f"beautiful woman, {prompt}"
    elif gender == "mixed":
        prompt = f"multiple people, group photo, {prompt}"

    payload: dict[str, Any] = {
        "init_images": [init_b64],
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": cfg.get("steps", 35),
        "denoising_strength": cfg.get("denoising_strength", 0.42),
        "sampler_name": "DPM++ 2M",
        "width": width,
        "height": height,
        "resize_mode": 1,
        "cfg_scale": cfg.get("cfg_scale", 8),
        "override_settings": {"sd_model_checkpoint": cfg.get("model_name")},
    }

    controlnet_model = cfg.get("controlnet_model")
    if controlnet_model:
        payload["alwayson_scripts"] = {
            "controlnet": {
                "args": [
                    {
                        "enabled": True,
                        "image": init_b64,
                        "module": "canny",
                        "model": controlnet_model,
                        "weight": cfg.get("controlnet_weight", 0.6),
                        "resize_mode": "Crop and Resize",
                        "pixel_perfect": True,
                        "guidance_start": 0.0,
                        "guidance_end": cfg.get("guidance_end", 1.0),
                        "threshold_a": 33.0,
                        "threshold_b": 100.0,
                        "control_mode": "ControlNet is more important",
                    }
                ]
            }
        }

    try:
        response = requests.post(SD_URL, json=payload, timeout=600)
        response.raise_for_status()
        return response.json()["images"][0]
    except Exception as exc:
        logger.warning("Stable Diffusion failed, returning local/original image: %s", exc)
        return local_filter(raw_path, style_key)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/main_page")
def main_page():
    return render_template("index.html")


@app.route("/upload_temp", methods=["POST"])
def upload_temp():
    data = request.get_json(force=True)
    image_data = data.get("image", "")
    session_id = str(uuid.uuid4())
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    save_data_url(image_data, session_dir / "raw.png")
    return jsonify({"session_id": session_id})


@app.route("/transform", methods=["POST"])
def transform():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    style_key = data.get("style", "none")
    gender = data.get("gender")
    raw_path = TEMP_DIR / session_id / "raw.png"
    if not raw_path.exists():
        return jsonify({"error": "raw image not found"}), 404

    result_b64 = stable_diffusion_transform(raw_path, style_key, gender)
    preview_path = PREVIEW_DIR / f"{session_id}.png"
    preview_path.write_bytes(base64.b64decode(result_b64))
    return jsonify({"state": "SUCCESS", "preview_image": f"data:image/png;base64,{result_b64}"})


@app.route("/finalize", methods=["POST"])
def finalize():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    hash_value = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]

    public_folder = PUBLIC_DIR / hash_value
    public_folder.mkdir(parents=True, exist_ok=True)

    raw_src = TEMP_DIR / session_id / "raw.png"
    preview_src = PREVIEW_DIR / f"{session_id}.png"
    if not raw_src.exists() or not preview_src.exists():
        return jsonify({"error": "session files missing"}), 404

    shutil.copy(raw_src, public_folder / "raw.png")
    shutil.move(str(preview_src), public_folder / "result.png")

    download_url = f"{get_base_url()}/dl/{hash_value}/"
    qr = qrcode.make(download_url)
    qr_path = QR_DIR / f"{hash_value}.png"
    qr.save(qr_path)

    return jsonify({
        "download_url": download_url,
        "qrcode_b64": image_to_data_url(qr_path),
    })


@app.route("/dl/<folder>/")
def download_page(folder: str):
    return render_template("download.html", folder=folder, lan_url=f"{get_base_url()}/main_page")


@app.route("/public/<folder>/<filename>")
def serve_public(folder: str, filename: str):
    return send_from_directory(PUBLIC_DIR / folder, filename)


@app.route("/admin")
def admin_page():
    return render_template("admin.html", admin_password=ADMIN_PASSWORD)


@app.route("/admin_data")
def admin_data():
    items: list[dict[str, Any]] = []
    for folder in PUBLIC_DIR.iterdir():
        if folder.is_dir() and (folder / "result.png").exists():
            timestamp = (folder / "result.png").stat().st_mtime
            items.append({
                "folder": folder.name,
                "time": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": timestamp,
            })
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return jsonify(items)


if __name__ == "__main__":
    logger.info("Kobe Studio running at http://127.0.0.1:5000/main_page")
    logger.info("LAN URL: %s/main_page", get_base_url())
    app.run(host="0.0.0.0", port=5000, debug=True)
