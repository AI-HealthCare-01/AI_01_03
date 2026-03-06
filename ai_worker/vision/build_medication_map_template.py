from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _normalize_medication_id(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    if not normalized:
        return ""
    if "_" not in normalized:
        return f"{normalized}_PILL"
    return normalized


def _collect_drug_name_map(json_root: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for jf in sorted(json_root.rglob("*.json")):
        try:
            payload = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        images = payload.get("images", [])
        if not images:
            continue
        image_meta = images[0]
        drug_n = str(image_meta.get("drug_N", "")).strip()
        dl_name = str(image_meta.get("dl_name", "")).strip()
        if not drug_n or not dl_name:
            continue
        mapping.setdefault(drug_n, dl_name)
    return mapping


def build_template(labels_path: Path, out_path: Path, *, fill_identity: bool = False) -> None:
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(label, str) for label in payload):
        raise ValueError("labels.json must be a JSON array of class label strings")

    template = {
        label: (_normalize_medication_id(label) if fill_identity else "")
        for label in payload
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] wrote template: {out_path.resolve()}")
    print(f"[INFO] labels: {len(payload)}")


def build_template_with_metadata(
    labels_path: Path,
    out_path: Path,
    json_root: Path,
    *,
    fill_identity: bool = False,
) -> None:
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(label, str) for label in payload):
        raise ValueError("labels.json must be a JSON array of class label strings")

    name_map = _collect_drug_name_map(json_root)
    template: dict[str, str] = {}
    filled = 0
    for label in payload:
        dl_name = name_map.get(label, "")
        medication_id = _normalize_medication_id(dl_name) if dl_name else ""
        if not medication_id and fill_identity:
            medication_id = _normalize_medication_id(label)
        template[label] = medication_id
        if medication_id:
            filled += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] wrote template: {out_path.resolve()}")
    print(f"[INFO] labels: {len(payload)}")
    print(f"[INFO] mapped_from_metadata: {filled}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="classifier labels 기반 medication_id 매핑 템플릿 생성")
    parser.add_argument(
        "--labels",
        type=Path,
        default=Path("runs/classify/runs/classify/pill_cls_finetune_v1/labels.json"),
        help="YOLO 분류 학습 결과 labels.json 경로",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("app/resources/vision_medication_map.json"),
        help="생성할 medication 매핑 템플릿 경로",
    )
    parser.add_argument(
        "--json-root",
        type=Path,
        default=None,
        help="선택: 원본 라벨 JSON 루트(VL_2_단일 등). 있으면 dl_name 기반으로 값 자동 채움",
    )
    parser.add_argument(
        "--fill-identity",
        action="store_true",
        help="매핑값이 비어있을 때 label 자체를 medication_id(K_040221 형태)로 채움",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.json_root:
        build_template_with_metadata(
            labels_path=args.labels,
            out_path=args.out,
            json_root=args.json_root,
            fill_identity=args.fill_identity,
        )
    else:
        build_template(labels_path=args.labels, out_path=args.out, fill_identity=args.fill_identity)
