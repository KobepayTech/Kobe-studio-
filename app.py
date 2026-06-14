from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import queue
import shutil
import socket
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np
import qrcode
import requests
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
PUBLIC_DIR = BASE_DIR / "public"
PREVIEW_DIR = BASE_DIR / "static" / "preview"
QR_DIR = BASE_DIR / "static" / "qr"
DB_PATH = BASE_DIR / "kobe_studio.db"

for folder in (TEMP_DIR, PUBLIC_DIR, PREVIEW_DIR, QR_DIR):
    folder.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("kobe-studio")

app = Flask(__name__)
app.secret_key = os.getenv("KOBE_SECRET_KEY", "change-this-secret-before-production")

ADMIN_PASSWORD = os.getenv("KOBE_ADMIN_PASSWORD", "admin")
DEFAULT_SD_URL = os.getenv("KOBE_SD_URL", "http://127.0.0.1:7860/sdapi/v1/img2img")
TASK_QUEUE: queue.Queue[str] = queue.Queue()
WORKER_STARTED = False


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guests (
                id TEXT PRIMARY KEY,
                name TEXT,
                contact TEXT,
                consent INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                public_id TEXT,
                guest_id TEXT,
                event_name TEXT,
                style TEXT,
                gender TEXT,
                camera_mode TEXT,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                message TEXT,
                raw_path TEXT,
                result_path TEXT,
                qr_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(guest_id) REFERENCES guests(id)
            )
            """
        )
        defaults = {
            "event_name": "Kobe Studio Event",
            "brand_color": "#2563eb",
            "sd_url": DEFAULT_SD_URL,
            "tunnel_url": "",
            "printer_name": "",
            "print_enabled": "true",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def get_setting(key: str, default: str = "") -> str:
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_all_settings() -> dict[str, str]:
    with db_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    return {row["key"]: row["value"] for row in rows}


def update_session(session_id: str, **fields: Any) -> None:
    fields["updated_at"] = now_iso()
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [session_id]
    with db_conn() as conn:
        conn.execute(f"UPDATE sessions SET {columns} WHERE id = ?", values)


def get_session_record(session_id: str) -> dict[str, Any] | None:
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row_to_dict(row)


def list_session_records(limit: int = 100) -> list[dict[str, Any]]:
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row_to_dict(row) for row in rows if row]


def admin_required(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not session.get("admin_ok"):
            return redirect(url_for("login_page"))
        return func(*args, **kwargs)

    return wrapper


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
    db_tunnel_url = get_setting("tunnel_url", "").strip()
    if db_tunnel_url:
        return db_tunnel_url.rstrip("/")

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

    model_name = cfg.get("model_name")
    if not model_name or model_name == "put_your_model_here":
        return local_filter(raw_path, style_key)

    image = Image.open(raw_path).convert("RGB")
    width, height = image.size
    init_b64 = base64.b64encode(raw_path.read_bytes()).decode("utf-8")

    base_prompt = cfg.get("prompt", "")
    if gender == "male":
        prompt = f"single person portrait, masculine presentation, {base_prompt}"
    elif gender == "female":
        prompt = f"single person portrait, feminine presentation, {base_prompt}"
    else:
        prompt = f"group or person portrait, {base_prompt}"

    payload: dict[str, Any] = {
        "init_images": [init_b64],
        "prompt": prompt,
        "negative_prompt": cfg.get("negative_prompt", "deformed, distorted, blurry"),
        "steps": cfg.get("steps", 35),
        "denoising_strength": cfg.get("denoising_strength", 0.42),
        "sampler_name": "DPM++ 2M",
        "width": width,
        "height": height,
        "resize_mode": 1,
        "cfg_scale": cfg.get("cfg_scale", 8),
        "override_settings": {"sd_model_checkpoint": model_name},
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

    sd_url = get_setting("sd_url", DEFAULT_SD_URL)
    try:
        response = requests.post(sd_url, json=payload, timeout=600)
        response.raise_for_status()
        return response.json()["images"][0]
    except Exception as exc:
        logger.warning("Stable Diffusion failed, returning local/original image: %s", exc)
        return local_filter(raw_path, style_key)


def complete_session(session_id: str, result_b64: str) -> dict[str, Any]:
    record = get_session_record(session_id)
    if not record:
        raise RuntimeError("Session not found")

    public_id = record.get("public_id") or hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    public_folder = PUBLIC_DIR / public_id
    public_folder.mkdir(parents=True, exist_ok=True)

    raw_src = Path(record["raw_path"])
    result_path = public_folder / "result.png"
    raw_path = public_folder / "raw.png"
    qr_path = QR_DIR / f"{public_id}.png"

    result_path.write_bytes(base64.b64decode(result_b64))
    shutil.copy(raw_src, raw_path)

    download_url = f"{get_base_url()}/dl/{public_id}/"
    qr = qrcode.make(download_url)
    qr.save(qr_path)

    update_session(
        session_id,
        public_id=public_id,
        status="completed",
        progress=100,
        message="Completed",
        result_path=str(result_path),
        qr_path=str(qr_path),
        error="",
    )
    return get_session_record(session_id) or {}


def process_session_job(session_id: str) -> None:
    record = get_session_record(session_id)
    if not record:
        return
    try:
        update_session(session_id, status="processing", progress=25, message="Processing image")
        raw_path = Path(record["raw_path"])
        result_b64 = stable_diffusion_transform(raw_path, record.get("style") or "none", record.get("gender"))
        update_session(session_id, status="processing", progress=85, message="Saving result and QR")
        complete_session(session_id, result_b64)
    except Exception as exc:
        logger.exception("Processing failed for %s", session_id)
        update_session(session_id, status="error", progress=100, message="Error", error=str(exc))


def worker_loop() -> None:
    while True:
        session_id = TASK_QUEUE.get()
        try:
            process_session_job(session_id)
        finally:
            TASK_QUEUE.task_done()


def start_worker() -> None:
    global WORKER_STARTED
    if WORKER_STARTED:
        return
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()
    WORKER_STARTED = True


@app.route("/")
def home():
    return render_template("index.html", settings=get_all_settings())


@app.route("/main_page")
def main_page():
    return render_template("index.html", settings=get_all_settings())


@app.route("/upload_temp", methods=["POST"])
def upload_temp():
    data = request.get_json(force=True)
    image_data = data.get("image", "")
    camera_mode = data.get("camera_mode", "unknown")
    guest_name = data.get("guest_name", "").strip()
    guest_contact = data.get("guest_contact", "").strip()

    session_id = str(uuid.uuid4())
    guest_id = None
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    raw_path = session_dir / "raw.png"
    save_data_url(image_data, raw_path)

    with db_conn() as conn:
        if guest_name or guest_contact:
            guest_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO guests (id, name, contact, consent, created_at) VALUES (?, ?, ?, ?, ?)",
                (guest_id, guest_name, guest_contact, 1, now_iso()),
            )
        conn.execute(
            """
            INSERT INTO sessions (
                id, guest_id, event_name, camera_mode, status, progress, message, raw_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                guest_id,
                get_setting("event_name", "Kobe Studio Event"),
                camera_mode,
                "uploaded",
                10,
                "Photo uploaded",
                str(raw_path),
                now_iso(),
                now_iso(),
            ),
        )
    return jsonify({"session_id": session_id, "status": "uploaded", "progress": 10})


@app.route("/transform", methods=["POST"])
def transform():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    style_key = data.get("style", "none")
    gender = data.get("gender", "mixed")
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404

    if record["status"] in {"queued", "processing"}:
        return jsonify({"session_id": session_id, "state": record["status"], "progress": record["progress"]}), 202

    if record["status"] == "completed":
        return jsonify({"session_id": session_id, "state": "completed", "progress": 100}), 200

    update_session(
        session_id,
        style=style_key,
        gender=gender,
        status="queued",
        progress=15,
        message="Queued for processing",
        error="",
    )
    TASK_QUEUE.put(session_id)
    return jsonify({"session_id": session_id, "state": "queued", "progress": 15}), 202


@app.route("/status/<session_id>")
def session_status(session_id: str):
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404
    download_url = None
    if record.get("public_id"):
        download_url = f"{get_base_url()}/dl/{record['public_id']}/"
    return jsonify({**record, "download_url": download_url})


@app.route("/finalize", methods=["POST"])
def finalize():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404
    if record["status"] != "completed" or not record.get("public_id"):
        return jsonify({"state": record["status"], "progress": record["progress"]}), 409
    public_id = record["public_id"]
    qr_path = QR_DIR / f"{public_id}.png"
    return jsonify({
        "download_url": f"{get_base_url()}/dl/{public_id}/",
        "qrcode_b64": image_to_data_url(qr_path) if qr_path.exists() else "",
    })


@app.route("/dl/<folder>/")
def download_page(folder: str):
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE public_id = ?", (folder,)).fetchone()
    record = row_to_dict(row) if row else {"public_id": folder, "event_name": get_setting("event_name")}
    return render_template(
        "download.html",
        folder=folder,
        record=record,
        settings=get_all_settings(),
        lan_url=f"{get_base_url()}/main_page",
    )


@app.route("/public/<folder>/<filename>")
def serve_public(folder: str, filename: str):
    return send_from_directory(PUBLIC_DIR / folder, filename)


@app.route("/login", methods=["GET", "POST"])
def login_page():
    error = ""
    if request.method == "POST":
        entered = request.form.get("password", "")
        if hmac.compare_digest(entered, ADMIN_PASSWORD):
            session["admin_ok"] = True
            return redirect(url_for("admin_page"))
        error = "Wrong admin password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout_page():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/admin")
@admin_required
def admin_page():
    records = list_session_records(200)
    return render_template("admin.html", sessions=records, settings=get_all_settings())


@app.route("/admin/settings", methods=["POST"])
@admin_required
def admin_settings():
    for key in ("event_name", "brand_color", "sd_url", "tunnel_url", "printer_name", "print_enabled"):
        if key in request.form:
            set_setting(key, request.form.get(key, ""))
    return redirect(url_for("admin_page"))


@app.route("/admin/sessions/<session_id>/delete", methods=["POST"])
@admin_required
def admin_delete_session(session_id: str):
    record = get_session_record(session_id)
    if not record:
        abort(404)
    for path_key in ("raw_path", "result_path", "qr_path"):
        value = record.get(path_key)
        if value:
            try:
                Path(value).unlink(missing_ok=True)
            except Exception:
                logger.warning("Could not remove %s", value)
    if record.get("public_id"):
        shutil.rmtree(PUBLIC_DIR / record["public_id"], ignore_errors=True)
    with db_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return redirect(url_for("admin_page"))


@app.route("/admin_data")
def admin_data():
    return jsonify(list_session_records(200))


@app.route("/api/settings", methods=["GET", "POST"])
@admin_required
def api_settings():
    if request.method == "POST":
        data = request.get_json(force=True)
        for key, value in data.items():
            set_setting(str(key), str(value))
    return jsonify(get_all_settings())


@app.route("/api/sd/models")
@admin_required
def api_sd_models():
    sd_url = get_setting("sd_url", DEFAULT_SD_URL)
    base = sd_url.split("/sdapi/", 1)[0]
    try:
        response = requests.get(f"{base}/sdapi/v1/sd-models", timeout=10)
        response.raise_for_status()
        models = [item.get("model_name") or item.get("title") for item in response.json()]
        return jsonify({"models": models})
    except Exception as exc:
        return jsonify({"models": [], "error": str(exc)}), 502


init_db()
start_worker()

if __name__ == "__main__":
    logger.info("Kobe Studio running at http://127.0.0.1:5000/main_page")
    logger.info("LAN URL: %s/main_page", get_base_url())
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
