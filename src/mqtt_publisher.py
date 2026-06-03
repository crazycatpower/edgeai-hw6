#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PublisherConfig:
    host: str = "localhost"
    port: int = 1883
    topic: str = "edgeai/detections"
    client_id: str = "edgeai-hw6"
    keepalive: int = 60


class MqttPublisher:
    def __init__(
        self,
        config: PublisherConfig | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._config = config or PublisherConfig()
        self._client = self._make_client(client_factory)
        self._connected = False

    def _make_client(self, factory: Callable[..., Any] | None) -> Any:
        if factory is not None:
            return factory(self._config.client_id)
        import paho.mqtt.client as mqtt  # pragma: no cover
        from paho.mqtt.enums import CallbackAPIVersion  # pragma: no cover

        # paho-mqtt 2.0+ requires callback_api_version; VERSION1 keeps
        # the legacy on_connect/on_message signature for compatibility.
        return mqtt.Client(  # pragma: no cover
            callback_api_version=CallbackAPIVersion.VERSION1,
            client_id=self._config.client_id,
        )

    def connect(self) -> None:
        self._client.connect(self._config.host, self._config.port, self._config.keepalive)
        self._client.loop_start()
        self._connected = True
        logger.info("MQTT connected to %s:%d", self._config.host, self._config.port)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
        logger.info("MQTT disconnected")

    def publish(self, payload: dict[str, Any] | str) -> bool:
        if not self._connected:
            logger.warning("MQTT not connected, dropping message")
            return False
        if isinstance(payload, dict):
            message = json.dumps(payload)
        else:
            message = payload
        self._client.publish(self._config.topic, message)
        return True
