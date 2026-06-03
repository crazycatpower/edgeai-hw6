#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import json
import logging
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

_MODEL_VERSION = "unknown"
_PORT = 8000


def _get_power_mode() -> str:
    try:
        result = subprocess.run(["nvpmodel", "-q"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if "NV Power Mode" in line:
                return line.split(":")[-1].strip()
        return "unknown"
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

    def start(self) -> None:
        self._server = HTTPServer(("", self._port), _HealthHandler)
        logger.info("HealthCheck listening on port %d", self._port)
        self._server.serve_forever()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


def start_in_thread(port: int = _PORT, model_version: str = "unknown") -> HealthCheckServer:
    server = HealthCheckServer(port=port, model_version=model_version)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    return server
