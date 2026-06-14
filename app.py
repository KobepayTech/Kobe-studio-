from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import queue
import shutil
import socket
import sqlite3
import subprocess
import threading
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
from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
PUBLIC_DIR = BASE_DIR / "public"
PREVIEW_DIR = BASE_DIR / "static" / "preview"
QR_DIR = BASE_DIR / "static" / "qr"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "kobe_studio.db"
CHECKPOINTS_PATH = BASE_DIR / "checkpoints.json"

for folder in (TEMP_DIR, PUBLIC_DIR, PREVIEW_DIR, QR_DIR, UPLOAD_DIR):
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
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS guests (id TEXT PRIMARY KEY, name TEXT, contact TEXT, consent INTEGER DEFAULT 0, created_at TEXT NOT NULL)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, public_id TEXT, guest_id TEXT, event_name TEXT, style TEXT,
                gender TEXT, camera_mode TEXT, status TEXT NOT NULL, progress INTEGER DEFAULT 0,
                message TEXT, raw_path TEXT, result_path TEXT, qr_path TEXT, error TEXT,
                gate_open INTEGER DEFAULT 0, gate_amount TEXT, print_status TEXT DEFAULT '',
                print_error TEXT DEFAULT '', printed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        migrations = {
            "gate_open": "ALTER TABLE sessions ADD COLUMN gate_open INTEGER DEFAULT 0",
            "gate_amount": "ALTER TABLE sessions ADD COLUMN gate_amount TEXT",
            "print_status": "ALTER TABLE sessions ADD COLUMN print_status TEXT DEFAULT ''",
            "print_error": "ALTER TABLE sessions ADD COLUMN print_error TEXT DEFAULT ''",
            "printed_at": "ALTER TABLE sessions ADD COLUMN printed_at TEXT",
        }
        for col, sql in migrations.items():
            if col not in existing:
                conn.execute(sql)
        defaults = {
            "event_name": "Kobe Studio Event",
            "brand_color": "#2563eb",
            "sd_url": DEFAULT_SD_URL,
            "tunnel_url": "",
            "printer_name": "",
            "print_enabled": "true",
            "auto_print_on_complete": "false",
            "gate_required": "false",
            "gate_key": "change-this-key",
            "gate_amount": "1",
            "logo_path": "",
        }
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {key: row[key] for key in row.keys()}


def get_setting(key: str, default: str = "") -> str:
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db_conn() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def get_all_settings() -> dict[str, str]:
    with db_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
    data = {row["key"]: row["value"] for row in rows}
    data["logo_url"] = f"/uploads/{data['logo_path']}" if data.get("logo_path") else ""
    return data


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


def get_session_by_public_id(public_id: str) -> dict[str, Any] | None:
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE public_id = ?", (public_id,)).fetchone()
    return row_to_dict(row)


def list_session_records(limit: int = 100) -> list[dict[str, Any]]:
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
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
    url = get_setting("tunnel_url", "").strip()
    if url:
        return url.rstrip("/")
    tunnel_file = BASE_DIR / "tunnel_url.txt"
    if tunnel_file.exists():
        value = tunnel_file.read_text(encoding="utf-8", errors="ignore").strip()
        if value:
            return value.rstrip("/")
    return f"http://{get_lan_ip()}:5000"


def read_checkpoint_file() -> dict[str, Any]:
    if not CHECKPOINTS_PATH.exists():
        return {"checkpoints": {}}
    return json.loads(CHECKPOINTS_PATH.read_text(encoding="utf-8"))


def write_checkpoint_file(data: dict[str, Any]) -> None:
    CHECKPOINTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_style_config() -> dict[str, Any]:
    return read_checkpoint_file().get("checkpoints", {})


def update_checkpoint_model(style_key: str, model_name: str) -> None:
    data = read_checkpoint_file()
    cfg = data.setdefault("checkpoints", {}).setdefault(style_key, {})
    cfg["model_name"] = model_name
    write_checkpoint_file(data)


def image_to_data_url(path: Path) -> str:
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode('utf-8')}"


def save_data_url(data_url: str, path: Path) -> None:
    if "," not in data_url:
        raise ValueError("Invalid image data URL")
    path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))


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
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
        ok, buffer = cv2.imencode(".png", rgb)
        if not ok:
            raise RuntimeError("OpenCV canny filter failed")
        return base64.b64encode(buffer).decode("utf-8")
    return base64.b64encode(raw_path.read_bytes()).decode("utf-8")


def stable_diffusion_transform(raw_path: Path, style_key: str, gender: str | None) -> str:
    cfg = dict(read_style_config().get(style_key, {}))
    model_name = cfg.get("model_name")
    if not model_name or model_name == "put_your_model_here":
        return local_filter(raw_path, style_key)
    image = Image.open(raw_path).convert("RGB")
    init_b64 = base64.b64encode(raw_path.read_bytes()).decode("utf-8")
    prompt = cfg.get("prompt", "")
    payload: dict[str, Any] = {
        "init_images": [init_b64],
        "prompt": prompt,
        "negative_prompt": cfg.get("negative_prompt", "deformed, distorted, blurry"),
        "steps": cfg.get("steps", 35),
        "denoising_strength": cfg.get("denoising_strength", 0.42),
        "sampler_name": "DPM++ 2M",
        "width": image.size[0],
        "height": image.size[1],
        "resize_mode": 1,
        "cfg_scale": cfg.get("cfg_scale", 8),
        "override_settings": {"sd_model_checkpoint": model_name},
    }
    try:
        response = requests.post(get_setting("sd_url", DEFAULT_SD_URL), json=payload, timeout=600)
        response.raise_for_status()
        return response.json()["images"][0]
    except Exception as exc:
        logger.warning("Stable Diffusion failed, returning local/original image: %s", exc)
        return local_filter(raw_path, style_key)


def print_image_file(image_path: Path, printer_name: str = "") -> tuple[bool, str]:
    if not image_path.exists():
        return False, f"Image not found: {image_path}"
    try:
        if platform.system().lower() == "windows":
            os.startfile(str(image_path), "print")  # type: ignore[attr-defined]
            return True, "Sent to Windows default printer"
        cmd = ["lp"]
        if printer_name:
            cmd += ["-d", printer_name]
        cmd.append(str(image_path))
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, "Sent to printer"
    except Exception as exc:
        return False, str(exc)


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
    qrcode.make(f"{get_base_url()}/dl/{public_id}/").save(qr_path)
    update_session(session_id, public_id=public_id, status="completed", progress=100, message="Completed", result_path=str(result_path), qr_path=str(qr_path), error="")
    if get_setting("auto_print_on_complete", "false") == "true" and get_setting("print_enabled", "true") == "true":
        ok, msg = print_image_file(result_path, get_setting("printer_name", ""))
        update_session(session_id, print_status="printed" if ok else "print_error", print_error="" if ok else msg, printed_at=now_iso() if ok else None)
    return get_session_record(session_id) or {}


def process_session_job(session_id: str) -> None:
    record = get_session_record(session_id)
    if not record:
        return
    try:
        update_session(session_id, status="processing", progress=25, message="Processing image")
        result_b64 = stable_diffusion_transform(Path(record["raw_path"]), record.get("style") or "none", record.get("gender"))
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
    if not WORKER_STARTED:
        threading.Thread(target=worker_loop, daemon=True).start()
        WORKER_STARTED = True


def gate_required_for_session(record: dict[str, Any]) -> bool:
    return get_setting("gate_required", "false") == "true" and not record.get("gate_open")


@app.route("/")
def home():
    return render_template("index.html", settings=get_all_settings())


@app.route("/main_page")
def main_page():
    return render_template("index.html", settings=get_all_settings())


@app.route("/uploads/<filename>")
def serve_upload(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/upload_temp", methods=["POST"])
def upload_temp():
    data = request.get_json(force=True)
    session_id = str(uuid.uuid4())
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    raw_path = session_dir / "raw.png"
    save_data_url(data.get("image", ""), raw_path)
    gate_open = 0 if get_setting("gate_required", "false") == "true" else 1
    guest_name = data.get("guest_name", "").strip()
    guest_contact = data.get("guest_contact", "").strip()
    guest_id = None
    with db_conn() as conn:
        if guest_name or guest_contact:
            guest_id = str(uuid.uuid4())
            conn.execute("INSERT INTO guests (id, name, contact, consent, created_at) VALUES (?, ?, ?, ?, ?)", (guest_id, guest_name, guest_contact, 1, now_iso()))
        conn.execute("""
            INSERT INTO sessions (id, guest_id, event_name, camera_mode, status, progress, message, raw_path, gate_open, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, guest_id, get_setting("event_name", "Kobe Studio Event"), data.get("camera_mode", "unknown"), "uploaded", 10, "Photo uploaded", str(raw_path), gate_open, now_iso(), now_iso()))
    return jsonify({"session_id": session_id, "status": "uploaded", "progress": 10, "gate_required": get_setting("gate_required", "false") == "true", "gate_open": bool(gate_open)})


@app.route("/transform", methods=["POST"])
def transform():
    data = request.get_json(force=True)
    session_id = data["session_id"]
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404
    if gate_required_for_session(record):
        update_session(session_id, status="waiting_gate", progress=15, message="Waiting for hardware trigger")
        return jsonify({"error": "hardware trigger required", "state": "waiting_gate", "progress": 15}), 402
    if record["status"] in {"queued", "processing"}:
        return jsonify({"session_id": session_id, "state": record["status"], "progress": record["progress"]}), 202
    if record["status"] == "completed":
        return jsonify({"session_id": session_id, "state": "completed", "progress": 100}), 200
    update_session(session_id, style=data.get("style", "none"), gender=data.get("gender", "mixed"), status="queued", progress=15, message="Queued for processing", error="")
    TASK_QUEUE.put(session_id)
    return jsonify({"session_id": session_id, "state": "queued", "progress": 15}), 202


@app.route("/status/<session_id>")
def session_status(session_id: str):
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404
    download_url = f"{get_base_url()}/dl/{record['public_id']}/" if record.get("public_id") else None
    return jsonify({**record, "download_url": download_url})


@app.route("/gate_status/<session_id>")
def gate_status(session_id: str):
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404
    return jsonify({"session_id": session_id, "gate_required": get_setting("gate_required", "false") == "true", "gate_open": bool(record.get("gate_open")), "gate_amount": record.get("gate_amount"), "status": record.get("status")})


@app.route("/api/hardware/trigger", methods=["POST"])
def hardware_trigger():
    data = request.get_json(force=True)
    if not hmac.compare_digest(data.get("key", ""), get_setting("gate_key", "change-this-key")):
        return jsonify({"error": "invalid key"}), 403
    session_id = data.get("session_id")
    if not session_id:
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE status IN ('uploaded', 'waiting_gate') ORDER BY created_at DESC LIMIT 1").fetchone()
        record = row_to_dict(row)
        if not record:
            return jsonify({"error": "no waiting session"}), 404
        session_id = record["id"]
    record = get_session_record(session_id)
    if not record:
        return jsonify({"error": "session not found"}), 404
    update_session(session_id, gate_open=1, gate_amount=str(data.get("amount", get_setting("gate_amount", "1"))), status="uploaded" if record.get("status") == "waiting_gate" else record.get("status"), message="Hardware trigger received")
    return jsonify({"ok": True, "session_id": session_id})


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
    return jsonify({"download_url": f"{get_base_url()}/dl/{public_id}/", "qrcode_b64": image_to_data_url(qr_path) if qr_path.exists() else ""})


@app.route("/dl/<folder>/")
def download_page(folder: str):
    record = get_session_by_public_id(folder) or {"public_id": folder, "event_name": get_setting("event_name")}
    return render_template("download.html", folder=folder, record=record, settings=get_all_settings(), lan_url=f"{get_base_url()}/main_page")


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
    return render_template("admin.html", sessions=list_session_records(200), settings=get_all_settings(), checkpoints=read_style_config())


@app.route("/admin/settings", methods=["POST"])
@admin_required
def admin_settings():
    for key in ("event_name", "brand_color", "sd_url", "tunnel_url", "printer_name", "print_enabled", "auto_print_on_complete", "gate_required", "gate_key", "gate_amount"):
        if key in request.form:
            set_setting(key, request.form.get(key, ""))
    return redirect(url_for("admin_page"))


@app.route("/admin/logo", methods=["POST"])
@admin_required
def admin_logo_upload():
    file = request.files.get("logo")
    if not file or not file.filename:
        return redirect(url_for("admin_page"))
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        abort(400, "Unsupported logo file type")
    filename = secure_filename(f"logo{ext}")
    for old in UPLOAD_DIR.glob("logo.*"):
        old.unlink(missing_ok=True)
    file.save(UPLOAD_DIR / filename)
    set_setting("logo_path", filename)
    return redirect(url_for("admin_page"))


@app.route("/admin/models", methods=["POST"])
@admin_required
def admin_update_model():
    style_key = request.form.get("style_key", "").strip()
    model_name = request.form.get("model_name", "").strip()
    if not style_key or not model_name:
        abort(400, "style_key and model_name are required")
    update_checkpoint_model(style_key, model_name)
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


@app.route("/admin/sessions/<session_id>/print", methods=["POST"])
@admin_required
def admin_print_session(session_id: str):
    record = get_session_record(session_id)
    if not record:
        abort(404)
    if not record.get("result_path"):
        abort(400, "No result image to print")
    ok, msg = print_image_file(Path(record["result_path"]), get_setting("printer_name", ""))
    update_session(session_id, print_status="printed" if ok else "print_error", print_error="" if ok else msg, printed_at=now_iso() if ok else None)
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
