from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TUNNEL_FILE = ROOT / "tunnel_url.txt"
URL_PATTERN = re.compile(r"https://[-a-zA-Z0-9.]+\.trycloudflare\.com")


def main() -> int:
    cmd = ["cloudflared", "tunnel", "--url", "http://localhost:5000"]
    print("Starting Cloudflare Tunnel:", " ".join(cmd), flush=True)
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        print("cloudflared was not found. Install Cloudflare Tunnel first.", file=sys.stderr)
        return 1

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        match = URL_PATTERN.search(line)
        if match:
            url = match.group(0)
            TUNNEL_FILE.write_text(url, encoding="utf-8")
            print(f"\nSaved public URL to {TUNNEL_FILE}: {url}\n", flush=True)
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
