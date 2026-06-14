from __future__ import annotations

import base64
import io
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402


def tiny_png_data_url() -> str:
    image = Image.new("RGB", (32, 32), color=(40, 90, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def main() -> int:
    client = app.test_client()

    upload = client.post(
        "/upload_temp",
        json={"image": tiny_png_data_url(), "camera_mode": "smoke-test"},
    )
    assert upload.status_code == 200, upload.get_data(as_text=True)
    session_id = upload.get_json()["session_id"]

    transform = client.post(
        "/transform",
        json={"session_id": session_id, "style": "none", "gender": "mixed"},
    )
    assert transform.status_code in (200, 202), transform.get_data(as_text=True)

    final_status = None
    for _ in range(20):
        status = client.get(f"/status/{session_id}")
        assert status.status_code == 200, status.get_data(as_text=True)
        final_status = status.get_json()
        if final_status["status"] == "completed":
            break
        time.sleep(0.5)

    assert final_status is not None
    assert final_status["status"] == "completed", final_status
    assert final_status["download_url"], final_status

    result_page = client.get(final_status["download_url"].replace("http://127.0.0.1:5000", ""))
    assert result_page.status_code == 200, result_page.get_data(as_text=True)

    print("Kobe Studio smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
