from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ultralytics import YOLO


def _load_label_names(weights: Path, label_file: Path | None) -> list[str]:
    candidate_paths: list[Path] = []
    if label_file is not None:
        candidate_paths.append(label_file)
    candidate_paths.append(weights.parent.parent / "labels.json")

    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, list) and payload and all(isinstance(item, str) for item in payload):
            return payload
    return []


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def infer(weights: Path, image: Path, topk: int, label_file: Path | None) -> dict[str, Any]:
    model = YOLO(str(weights))
    results = model(str(image))
    if not results:
        return {"image": str(image), "topk": []}

    probs = results[0].probs
    if probs is None:
        return {"image": str(image), "topk": []}

    top_idx = probs.top5[:topk]
    top_conf = probs.top5conf[:topk]
    label_names = _load_label_names(weights=weights, label_file=label_file)

    output: list[dict[str, Any]] = []
    for idx, conf in zip(top_idx, top_conf, strict=False):
        class_idx = int(idx)
        class_name = label_names[class_idx] if class_idx < len(label_names) else str(class_idx)
        output.append(
            {
                "class_id": class_idx,
                "class_name": class_name,
                "confidence": round(_safe_float(conf), 4),
            }
        )
    return {"image": str(image), "topk": output}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="fine-tuned YOLO 분류모델 추론")
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--labels", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = infer(weights=args.weights, image=args.image, topk=max(1, args.topk), label_file=args.labels)
    print(json.dumps(result, ensure_ascii=False, indent=2))
