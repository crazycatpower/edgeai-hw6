#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from unittest.mock import MagicMock, patch
import numpy as np
import pytest
import cv2

from src.inference_node import InferenceNode, CONFIDENCE_THRESHOLD, INPUT_SIZE


@pytest.fixture()
def node():
    return InferenceNode(client_factory=lambda cid: MagicMock())


@pytest.mark.parametrize(
    "shape",
    [
        (480, 640, 3),
        (720, 1280, 3),
        (240, 320, 3),
    ],
)
def test_preprocess_frame_output_shape(shape):
    frame = np.zeros(shape, dtype=np.uint8)
    result = InferenceNode.preprocess_frame(frame)
    assert result.shape == (INPUT_SIZE[1], INPUT_SIZE[0], 3)


def test_preprocess_frame_grayscale_converted():
    gray = np.zeros((480, 640), dtype=np.uint8)
    result = InferenceNode.preprocess_frame(gray)
    assert result.shape[2] == 3


def test_build_payload_format(node):
    detections = [{"class_id": 0, "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    payload = node._build_payload(detections, frame_id=42)
    assert payload["frame_id"] == 42
    assert payload["count"] == 1
    assert payload["detections"] == detections


def test_build_payload_empty_detections(node):
    payload = node._build_payload([], frame_id=0)
    assert payload["count"] == 0
    assert payload["detections"] == []


@pytest.mark.parametrize("conf,expected_count", [(0.3, 0), (0.6, 1), (0.9, 1)])
def test_confidence_threshold_filtering(node, conf, expected_count):
    mock_box = MagicMock()
    mock_box.conf = [conf]
    mock_box.cls = [0]
    mock_box.xyxy = [MagicMock(tolist=lambda: [0, 0, 10, 10])]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    with patch.object(node, "_model", create=True) as mock_model:
        mock_model.return_value = [mock_result]
        node._model = mock_model
        detections = node._run_inference(np.zeros((640, 640, 3), dtype=np.uint8))
    assert len(detections) == expected_count


def test_preprocess_preserves_dtype():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = InferenceNode.preprocess_frame(frame)
    assert result.dtype == np.uint8
