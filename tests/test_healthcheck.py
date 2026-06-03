#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from src.healthcheck import HealthCheckServer, _get_power_mode, start_in_thread


def test_get_power_mode_returns_string():
    result = _get_power_mode()
    assert isinstance(result, str)


def test_get_power_mode_nvpmodel_success():
    mock_result = MagicMock()
    mock_result.stdout = "NV Power Mode: 15W\n0\n"
    with patch("subprocess.run", return_value=mock_result):
        mode = _get_power_mode()
    assert mode == "15W"


def test_get_power_mode_nvpmodel_missing():
    with patch("subprocess.run", side_effect=Exception("not found")):
        mode = _get_power_mode()
    assert mode == "unavailable"


def test_healthcheck_server_healthz():
    server = HealthCheckServer(port=18081, model_version="v1.0.0")
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.3)
    try:
        with urllib.request.urlopen("http://localhost:18081/healthz", timeout=3) as resp:
            body = json.loads(resp.read())
        assert body["status"] == "healthy"
        assert body["model_version"] == "v1.0.0"
        assert "power_mode" in body
    finally:
        server.stop()


def test_healthcheck_server_404():
    server = HealthCheckServer(port=18082, model_version="test")
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.3)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen("http://localhost:18082/notfound", timeout=3)
        assert exc_info.value.code == 404
    finally:
        server.stop()


def test_start_in_thread_returns_server():
    server = start_in_thread(port=18083, model_version="thread-test")
    time.sleep(0.3)
    try:
        with urllib.request.urlopen("http://localhost:18083/healthz", timeout=3) as resp:
            body = json.loads(resp.read())
        assert body["status"] == "healthy"
    finally:
        server.stop()


def test_healthcheck_server_stop():
    server = HealthCheckServer(port=18084)
    t = threading.Thread(target=server.start, daemon=True)
    t.start()
    time.sleep(0.3)
    server.stop()
    time.sleep(0.1)
    with pytest.raises(Exception):
        urllib.request.urlopen("http://localhost:18084/healthz", timeout=1)


def test_get_power_mode_no_match():
    mock_result = MagicMock()
    mock_result.stdout = "some unrelated output\n"
    with patch("subprocess.run", return_value=mock_result):
        mode = _get_power_mode()
    assert mode == "unavailable"


def test_healthcheck_server_start_oserror():
    server = HealthCheckServer(port=19001)
    ready = threading.Event()
    with patch("src.healthcheck.HTTPServer", side_effect=OSError("address in use")):
        server.start(ready=ready)
    assert ready.is_set()


def test_start_in_thread_timeout_warning():
    with patch("threading.Event.wait", return_value=False):
        server = start_in_thread(port=18086, model_version="timeout-test")
    server.stop()
