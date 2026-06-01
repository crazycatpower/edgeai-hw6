#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CALIBRATION_DATA_DIR = Path(__file__).parent / "calibration_data"
OUTPUT_ENGINE = Path(__file__).parent.parent / "best_int8.engine"
BASELINE_JSON = Path(__file__).parent / "accuracy_baseline.json"
MODEL_PT = Path(__file__).parent.parent / "best.pt"


class Int8Calibrator:
    def __init__(
        self,
        model_path: Path = MODEL_PT,
        data_dir: Path = CALIBRATION_DATA_DIR,
        output_path: Path = OUTPUT_ENGINE,
    ) -> None:
        self._model_path = model_path
        self._data_dir = data_dir
        self._output_path = output_path

    def _md5(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def export(self) -> None:
        from ultralytics import YOLO  # pragma: no cover

        logger.info("Loading model from %s", self._model_path)
        model = YOLO(str(self._model_path))
        logger.info("Exporting INT8 engine to %s", self._output_path)
        model.export(
            format="engine",
            int8=True,
            data=str(Path(__file__).parent / "calibration.yaml"),
            imgsz=640,
            batch=1,
            workspace=4,
        )
        logger.info("Export complete")

    def evaluate(self, data_yaml: str, split: str = "test") -> float:
        from ultralytics import YOLO  # pragma: no cover

        model = YOLO(str(self._output_path))
        metrics = model.val(data=data_yaml, split=split)
        return float(metrics.box.map50)

    def write_baseline(
        self, fp16_map50: float, int8_map50: float, test_split: str = "test"
    ) -> None:
        import datetime

        md5 = self._md5(self._model_path) if self._model_path.exists() else "unknown"
        baseline = {
            "fp16_map50": round(fp16_map50, 4),
            "int8_map50": round(int8_map50, 4),
            "test_split": test_split,
            "calibrated_at": datetime.date.today().isoformat(),
            "best_pt_md5": md5,
        }
        with open(BASELINE_JSON, "w") as f:
            json.dump(baseline, f, indent=2)
        logger.info("Baseline written to %s", BASELINE_JSON)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    calibrator = Int8Calibrator()
    calibrator.export()


if __name__ == "__main__":
    main()
