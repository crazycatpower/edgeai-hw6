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
    # Skip pull if the image is already cached locally (pre-pulled in CI step).
    probe = subprocess.run(
        ["docker", "image", "inspect", IMAGE],
        capture_output=True,
        check=False,
    )
    if probe.returncode == 0:
        return
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


def _docker_logs(name: str, tail: int = 50) -> str:
    result = subprocess.run(
        ["docker", "logs", "--tail", str(tail), name],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + result.stderr


def _container_status(cid: str) -> str:
    result = subprocess.run(
        ["docker", "inspect", "--format={{.State.Status}}", cid],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def running_container():
    engine_path = Path(WORKSPACE) / "best_int8.engine"
    if not engine_path.exists():
        pytest.skip(f"best_int8.engine not found at {engine_path}")

    _pull_image()
    subprocess.run(["docker", "rm", "-f", "ci-edgeai-test"], check=False, timeout=10)
    time.sleep(2)  # ensure port 8000 is released before re-binding

    cid = _start_container(str(engine_path))

    # Give the container a moment to initialise before tests start polling.
    time.sleep(5)
    status = _container_status(cid)
    if status != "running":
        logs = _docker_logs("ci-edgeai-test")
        pytest.fail(f"Container exited early (status={status!r}).\n--- docker logs ---\n{logs}")

    yield cid

    print("\n--- docker logs (last 50 lines) ---")
    print(_docker_logs("ci-edgeai-test"))
    subprocess.run(["docker", "rm", "-f", cid], check=False, timeout=15)


def test_container_healthcheck_responds(running_container):
    if not _wait_for_healthz(timeout=60):
        logs = _docker_logs("ci-edgeai-test")
        pytest.fail(
            "Healthcheck did not respond within 60 s — Connection refused.\n"
            "--- docker logs ---\n" + logs
        )


def test_healthz_returns_healthy(running_container):
    _wait_for_healthz(timeout=30)
    with urllib.request.urlopen("http://localhost:8000/healthz", timeout=5) as resp:
        body = json.loads(resp.read())
    assert body["status"] == "healthy"
    assert "model_version" in body
    assert "power_mode" in body
