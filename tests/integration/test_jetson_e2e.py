#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

REGISTRY = os.environ.get("REGISTRY", "ghcr.io")
REPO = os.environ.get("GITHUB_REPOSITORY", "unknown/edgeai-hw6")
SHA = os.environ.get("GITHUB_SHA", "local")[:7]
IMAGE = f"{REGISTRY}/{REPO}:sha-{SHA}"
WORKSPACE = os.environ.get("GITHUB_WORKSPACE", str(Path(__file__).parent.parent.parent))


def _pull_image() -> None:
    subprocess.run(["docker", "pull", IMAGE], check=True, timeout=600)


def _start_container(engine_path: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--runtime",
            "nvidia",
            "--network",
            "host",
            "--name",
            "ci-edgeai-test",
            "-v",
            f"{engine_path}:/opt/models/best_int8.engine:ro",
            "-e",
            "MODEL_PATH=/opt/models/best_int8.engine",
            IMAGE,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def _wait_for_healthz(host: str = "localhost", port: int = 8000, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/healthz", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


@pytest.fixture(scope="module")
def running_container():
    engine_path = Path(WORKSPACE) / "best_int8.engine"
    if not engine_path.exists():
        pytest.skip(f"best_int8.engine not found at {engine_path}")

    _pull_image()
    subprocess.run(["docker", "rm", "-f", "ci-edgeai-test"], check=False, timeout=10)
    cid = _start_container(str(engine_path))
    yield cid
    subprocess.run(["docker", "rm", "-f", cid], check=False, timeout=15)


def test_container_healthcheck_responds(running_container):
    assert _wait_for_healthz(timeout=60), (
        "Healthcheck did not respond within 60 seconds — check: docker logs ci-edgeai-test"
    )


def test_healthz_returns_healthy(running_container):
    _wait_for_healthz(timeout=30)
    with urllib.request.urlopen("http://localhost:8000/healthz", timeout=5) as resp:
        body = json.loads(resp.read())
    assert body["status"] == "healthy"
    assert "model_version" in body
    assert "power_mode" in body
