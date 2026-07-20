import json
import logging
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from nse_monitor.nse_client import NSEClient

logger = logging.getLogger("nse_monitor.health")

VERSION = "2.0.0"

_last_poll_time: str = "never"
_poll_lock = threading.Lock()


def set_last_poll_time(ts: str | None = None) -> None:
    global _last_poll_time
    with _poll_lock:
        _last_poll_time = ts or datetime.now(timezone.utc).isoformat()


def get_last_poll_time() -> str:
    with _poll_lock:
        return _last_poll_time


class HealthHandler(BaseHTTPRequestHandler):
    notification_status: str = "ok"

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        client: NSEClient = self.server.client
        cb_state = client.circuit_state.value

        payload: dict[str, Any] = {
            "last_successful_poll": get_last_poll_time(),
            "database_status": "ok",
            "notification_status": self.server.notification_status,
            "circuit_breaker_state": cb_state,
            "uptime_seconds": int(time.time() - self.server.start_time),
            "version": VERSION,
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug(fmt, *args)


def start_health_server(
    host: str, port: int, client: NSEClient
) -> HTTPServer:
    server = HTTPServer((host, port), HealthHandler)
    server.client = client
    server.start_time = time.time()
    server.notification_status = "ok"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on %s:%d", host, port)
    return server
