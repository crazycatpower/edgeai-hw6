#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

SAMPLE_FRAME = Path(__file__).parent / "sample_frame.jpg"
REGISTRY = os.environ.get("REGISTRY", "ghcr.io")
REPO = os.environ.get("GITHUB_REPOSITORY", "unknown/edgeai-hw6")
SHA = os.environ.get("GITHUB_SHA", "local")[:7]
IMAGE = f"{REGISTRY}/{REPO}:sha-{SHA}"

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = "edgeai/detections"


def _pull_and_run_container() -> str:
    subprocess.run(["docker", "pull", IMAGE], check=True, timeout=600)
    use_camera = Path("/dev/video0").exists()
    device_args = ["--device", "/dev/video0"] if use_camera else []
    frame_mount = (
        []
        if use_camera
        else ["-v", f"{SAMPLE_FRAME.resolve()}:/opt/data/sample_frame.jpg:ro"]
    )
    result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--runtime",
            "nvidia",
            "--network",
            "host",
            "-v",
            "lab12-models:/opt/models",
            *device_args,
            *frame_mount,
            IMAGE,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def container_id():
    cid = _pull_and_run_container()
    yield cid
    subprocess.run(["docker", "rm", "-f", cid], check=False)


def test_inference_publishes_mqtt(container_id):
    import paho.mqtt.client as mqtt  # pragma: no cover

    received = threading.Event()
    messages: list[str] = []

    def on_message(client, userdata, msg):
        messages.append(msg.payload.decode())
        received.set()

    client = mqtt.Client("e2e-test-subscriber")
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()

    try:
        assert received.wait(timeout=30), "No MQTT message received within 30 seconds"
        assert len(messages) >= 1
    finally:
        client.loop_stop()
        client.disconnect()
