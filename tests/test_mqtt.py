#!/usr/bin/env python3
# Copyright (c) 2026 黃義鈞, 李軒杰
# Tatung University — I4210 AI實務專題

import json
from unittest.mock import MagicMock

import pytest

from src.mqtt_publisher import MqttPublisher, PublisherConfig


@pytest.fixture()
def mock_client():
    return MagicMock()


@pytest.fixture()
def publisher(mock_client):
    config = PublisherConfig(host="localhost", port=1883, topic="test/topic")
    pub = MqttPublisher(config=config, client_factory=lambda cid: mock_client)
    pub.connect()
    return pub, mock_client


def test_publish_dict_sends_json(publisher):
    pub, client = publisher
    payload = {"frame_id": 1, "detections": [], "count": 0}
    result = pub.publish(payload)
    assert result is True
    client.publish.assert_called_once_with("test/topic", json.dumps(payload))


def test_publish_when_disconnected_returns_false():
    config = PublisherConfig()
    pub = MqttPublisher(config=config, client_factory=lambda cid: MagicMock())
    result = pub.publish({"frame_id": 0})
    assert result is False


def test_publish_string_not_double_encoded(publisher):
    pub, client = publisher
    raw = '{"already": "json"}'
    pub.publish(raw)
    client.publish.assert_called_once_with("test/topic", raw)


def test_disconnect_stops_loop(publisher):
    pub, client = publisher
    pub.disconnect()
    client.loop_stop.assert_called_once()
    client.disconnect.assert_called_once()


def test_connect_calls_loop_start(mock_client):
    config = PublisherConfig()
    pub = MqttPublisher(config=config, client_factory=lambda cid: mock_client)
    pub.connect()
    mock_client.loop_start.assert_called_once()


def test_publish_multiple_messages(publisher):
    pub, client = publisher
    for i in range(3):
        pub.publish({"frame_id": i})
    assert client.publish.call_count == 3
