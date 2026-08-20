from __future__ import annotations

import os
import runpy
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from api_layer.server import api


ROOT = Path(__file__).resolve().parent


def main() -> None:
    api_port = int(os.getenv("ENERJI_API_PORT", "8091"))
    api_url = f"http://127.0.0.1:{api_port}"
    os.environ["ENERJI_API_URL"] = api_url

    config = uvicorn.Config(
        api,
        host="127.0.0.1",
        port=api_port,
        access_log=False,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    api_thread = threading.Thread(
        target=server.run, name="energy-http-api", daemon=True
    )
    api_thread.start()

    for _ in range(80):
        try:
            with urlopen(f"{api_url}/api/v1/health", timeout=2) as response:
                if response.status == 200:
                    break
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(0.25)
    else:
        server.should_exit = True
        raise RuntimeError(f"Enerji HTTP API başlatılamadı: {api_url}")

    try:
        runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
    finally:
        server.should_exit = True
        api_thread.join(timeout=10)


if __name__ == "__main__":
    main()
