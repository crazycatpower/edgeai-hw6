#!/usr/bin/env python3
# Copyright (c) 2026 黃義鈞, 李軒杰
# Tatung University — I4210 AI實務專題

from unittest.mock import MagicMock

from src.inference_node import InferenceNode
from src.mqtt_publisher import MqttPublisher


def test_mqtt_publisher_instantiates():
    pub = MqttPublisher(client_factory=lambda cid: MagicMock())
    assert pub is not None


def test_inference_node_instantiates():
    node = InferenceNode(client_factory=lambda cid: MagicMock())
    assert node is not None


def test_healthcheck_server_instantiates():
    from src.healthcheck import HealthCheckServer

    server = HealthCheckServer(port=18000, model_version="test")
    assert server is not None
