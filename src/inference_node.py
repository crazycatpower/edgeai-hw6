#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from src.mqtt_publisher import MqttPublisher, PublisherConfig

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.5
INPUT_SIZE = (640, 640)


class InferenceNode:
    def __init__(
        self,
        model_path: str = "/opt/models/best_int8.engine",
        config: PublisherConfig | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._model_path = model_path
        self._publisher = MqttPublisher(config=config, client_factory=client_factory)
        self._model: Any = None

    def _load_model(self) -> None:
        from ultralytics import YOLO  # pragma: no cover

        self._model = YOLO(self._model_path)  # pragma: no cover

    @staticmethod
    def preprocess_frame(frame: np.ndarray) -> np.ndarray:
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        resized = cv2.resize(frame, INPUT_SIZE)
        return resized

    def _build_payload(self, detections: list[dict[str, Any]], frame_id: int) -> dict[str, Any]:
        return {
            "frame_id": frame_id,
            "detections": detections,
            "count": len(detections),
        }

    def _run_inference(self, frame: np.ndarray) -> list[dict[str, Any]]:  # pragma: no cover
        results = self._model(frame)
        detections = []
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE_THRESHOLD:
                    continue
                detections.append(
                    {
                        "class_id": int(box.cls[0]),
                        "confidence": conf,
                        "bbox": box.xyxy[0].tolist(),
                    }
                )
        return detections

    def run(self, source: str = "/dev/video0") -> None:  # pragma: no cover
        self._load_model()
        self._publisher.connect()
        cap = cv2.VideoCapture(source)
        frame_id = 0
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                processed = self.preprocess_frame(frame)
                detections = self._run_inference(processed)
                payload = self._build_payload(detections, frame_id)
                self._publisher.publish(payload)
                frame_id += 1
        finally:
            cap.release()
            self._publisher.disconnect()


def main() -> None:  # pragma: no cover
    import time

    from src import healthcheck

    healthcheck.start_in_thread()
    node = InferenceNode()
    try:
        node.run()
    except Exception as exc:
        logger.error("Inference loop exited: %s", exc)
    # Keep the process alive so the healthz daemon thread stays up even
    # when the inference loop ends (e.g. no camera, EOF on video source).
    while True:
        time.sleep(60)


if __name__ == "__main__":  # pragma: no cover
    main()
