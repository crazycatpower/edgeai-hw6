#!/usr/bin/env python3
# Copyright (c) 2026 黃義鈞, 李軒杰
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

_MODEL_VERSION = "unknown"
_PORT = 8000


def _get_power_mode() -> str:
    try:
        result = subprocess.run(
            ["nvpmodel", "-q"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"NV Power Mode:\s+(\S+)", result.stdout)
        if match:
            return match.group(1)
        return "unavailable"
    except Exception:
        return "unavailable"


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            body = json.dumps(
                {
                    "status": "healthy",
                    "model_version": _MODEL_VERSION,
                    "power_mode": _get_power_mode(),
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:  # silence default logs
        pass


class HealthCheckServer:
    def __init__(self, port: int = _PORT, model_version: str = "unknown") -> None:
        global _MODEL_VERSION
        self._port = port
        _MODEL_VERSION = model_version
        self._server: HTTPServer | None = None

    def start(self, ready: threading.Event | None = None) -> None:
        try:
            # Bind explicitly to 0.0.0.0 so the endpoint is reachable from the host
            # when the container runs with --network host.
            self._server = HTTPServer(("0.0.0.0", self._port), _HealthHandler)
            logger.info("HealthCheck listening on 0.0.0.0:%d", self._port)
            if ready is not None:
                ready.set()
            self._server.serve_forever()
        except OSError as exc:
            logger.error("HealthCheck failed to bind port %d: %s", self._port, exc)
            if ready is not None:
                ready.set()  # unblock caller even on failure

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


def start_in_thread(port: int = _PORT, model_version: str = "unknown") -> HealthCheckServer:
    server = HealthCheckServer(port=port, model_version=model_version)
    ready = threading.Event()
    thread = threading.Thread(target=server.start, args=(ready,), daemon=True)
    thread.start()
    # Wait up to 5 s for the server to bind before returning to the caller.
    if not ready.wait(timeout=5):
        logger.warning("HealthCheck server did not signal ready within 5 s")
    return server
