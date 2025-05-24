from __future__ import annotations
import os
import asyncio
import uuid
import logging
import time
from datetime import datetime, UTC
from typing import Any, Dict
from httpx import AsyncClient

# OS and browser activity imports
import psutil
import win32gui
import win32process
import pychrome  # type: ignore[import]

# Ensure log directory exists
LOG_DIR = os.path.join("Heti", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "live_signal.log")

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s – %(name)s – %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("monitor_embedder")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s – %(name)s – %(message)s"))
logger.addHandler(console_handler)

# HTTP client settings
TIMEOUT = 10.0
RETRIES = 3

def get_active_window_info() -> Dict[str, str]:
    """
    Returns the active window's title and process name.
    """
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd) or ""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid).name()
    except Exception:
        process = ""
    return {"title": title, "process": process}

def get_active_browser_info() -> Dict[str, str]:
    """
    Returns the active Chrome tab's title and URL via the remote-debugging interface.
    Chrome must be started with --remote-debugging-port=9222.
    """
    try:
        browser = pychrome.Browser(url="http://127.0.0.1:9222")
        for tab in browser.list_tab():
            if tab.get("type") == "page" and tab.get("active", False):
                return {
                    "tab_title": tab.get("title", ""),
                    "tab_url": tab.get("url", "")
                }
    except Exception:
        pass
    return {"tab_title": "", "tab_url": ""}

async def post_with_retries(client: AsyncClient, url: str, json_data: Dict[str, Any]) -> Any:
    for attempt in range(1, RETRIES + 1):
        try:
            return await client.post(url, json=json_data, timeout=TIMEOUT)
        except Exception:
            if attempt == RETRIES:
                raise
            await asyncio.sleep(2 ** (attempt - 1))

async def monitor_live(interval: float = 5.0, duration: float = 30.0) -> None:
    start_ts = datetime.now(UTC).isoformat() + "Z"
    banner = f"BEGIN LIVE MONITOR at {start_ts}"
    print(banner)
    logger.info(banner)

    invoke_url = (
        "http://localhost:8001/mcp/testclient/invoke/"
        "activity_embedder/default_user"
    )

    async with AsyncClient() as client:
        start_time = time.perf_counter()
        while duration <= 0 or time.perf_counter() - start_time < duration:
            ts = datetime.now(UTC).isoformat() + "Z"
            win = get_active_window_info()
            brw = get_active_browser_info()
            parts = []
            if win["title"]:
                parts.append(f"Window: {win['title']} ({win['process']})")
            if brw["tab_title"]:
                parts.append(f"Browser: {brw['tab_title']} ({brw['tab_url']})")
            message = "; ".join(parts) or "No active window or browser tab"

            entry = {
                "timestamp": ts,
                "window_title": win["title"],
                "process": win["process"],
                "tab_title": brw["tab_title"],
                "tab_url": brw["tab_url"],
                "message": message,
            }
            payload = {
                "log_batch": [entry],
                "meta": {
                    "category": "monitor_live",
                    "source": "monitor_embedder_live",
                    "loop_id": str(uuid.uuid4()),
                },
            }
            # Orchestration: ask eddi_g tool if we should proceed
            orc_url = invoke_url.replace("activity_embedder", "eddi_g")
            orc_resp = await post_with_retries(client, orc_url, payload)
            orc_data = orc_resp.json()
            if orc_data.get("status") != "ok":
                logger.warning("Orchestration: eddi_g blocked storage")
                await asyncio.sleep(interval)
                continue
            # Proceed with embedding and storage
            t0 = time.perf_counter()
            resp = await post_with_retries(client, invoke_url, payload)
            latency_us = (time.perf_counter() - t0) * 1_000_000
            resp.raise_for_status()
            data = resp.json()
            memory_id = data.get("memory_id", "")
            log_msg = f"✔ Stored memory {memory_id} in {latency_us:.0f}µs"
            logger.info(log_msg)
            print(log_msg)
            await asyncio.sleep(interval)

    complete_msg = "LIVE MONITOR COMPLETE"
    logger.info(complete_msg)
    print(complete_msg)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monitor embedder live loop")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between captures")
    parser.add_argument("--duration", type=float, default=30.0, help="Total run duration in seconds")
    args = parser.parse_args()
    asyncio.run(monitor_live(interval=args.interval, duration=args.duration))
