from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image
from ultralytics import YOLO

from ai_worker.core import default_logger

_classifier_model: YOLO | None = None
_classifier_model_path: Path | None = None
_classifier_labels: list[str] = []


def _load_labels(labels_path: Path | None) -> list[str]:
    if labels_path is None or not labels_path.exists():
        return []
    try:
        payload = json.loads(labels_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list) and all(isinstance(item, str) for item in payload):
        return payload
    return []


def get_classifier(model_path: str, labels_path: str | None = None) -> tuple[YOLO, list[str]]:
    global _classifier_model
    global _classifier_model_path
    global _classifier_labels

    model_path_obj = Path(model_path).resolve()
    if _classifier_model is None or _classifier_model_path != model_path_obj:
        default_logger.info("[CLS] Loading model: %s", model_path_obj)
        _classifier_model = YOLO(str(model_path_obj))
        _classifier_model_path = model_path_obj
        if labels_path:
            _classifier_labels = _load_labels(Path(labels_path).resolve())
        else:
            _classifier_labels = _load_labels(model_path_obj.parent.parent / "labels.json")

    return _classifier_model, _classifier_labels


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def predict_classes(
    *,
    image: Image.Image,
    model_path: str,
    labels_path: str | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    model, labels = get_classifier(model_path=model_path, labels_path=labels_path)
    results = model(image, verbose=False)
    if not results:
        return []

    probs = results[0].probs
    if probs is None:
        return []

    names = getattr(model, "names", {})
    top_idx = probs.top5[: max(1, top_k)]
    top_conf = probs.top5conf[: max(1, top_k)]

    output: list[dict[str, Any]] = []
    for idx, conf in zip(top_idx, top_conf, strict=False):
        class_id = int(idx)
        class_name = ""
        if class_id < len(labels):
            class_name = labels[class_id]
        elif isinstance(names, dict):
            class_name = str(names.get(class_id, class_id))
        else:
            class_name = str(class_id)

        output.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "confidence": _to_float(conf),
            }
        )
    return output
