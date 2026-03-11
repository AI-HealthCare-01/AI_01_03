#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

INPUT_DEFAULT = Path("runs/vision_samples/records.jsonl")
OUTPUT_DEFAULT = Path("runs/vision_samples/review_queue.jsonl")

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}

REASON_TO_PRIORITY = {
    "VISION_INTERNAL_ERROR": "P0",
    "VISION_TIMEOUT": "P0",
    "VISION_UPSTREAM_ERROR": "P0",
    "NO_PILL_DETECTED": "P1",
    "LOW_CONFIDENCE": "P2",
    "UNKNOWN_FAILURE": "P2",
    "UNKNOWN_PILL": "P3",
    "BORDERLINE_CONFIDENCE": "P3",
    "LOW_MARGIN": "P3",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_candidates(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        medication_id = str(item.get("medication_id", "")).strip()
        confidence = _safe_float(item.get("confidence", 0.0), 0.0)
        cleaned.append({"medication_id": medication_id, "confidence": confidence})
    return cleaned


def _calc_margin(candidates: list[dict[str, Any]]) -> float | None:
    if len(candidates) < 2:
        return None
    sorted_conf = sorted((_safe_float(c.get("confidence", 0.0), 0.0) for c in candidates), reverse=True)
    if len(sorted_conf) < 2:
        return None
    return round(sorted_conf[0] - sorted_conf[1], 4)


def _top1_info(record: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[str, float]:
    top1_medication_id = str(record.get("top1_medication_id", "")).strip()
    top1_confidence = _safe_float(record.get("top1_confidence", 0.0), 0.0)

    if (not top1_medication_id or top1_confidence <= 0.0) and candidates:
        top1 = max(candidates, key=lambda c: _safe_float(c.get("confidence", 0.0), 0.0))
        if not top1_medication_id:
            top1_medication_id = str(top1.get("medication_id", "")).strip()
        if top1_confidence <= 0.0:
            top1_confidence = _safe_float(top1.get("confidence", 0.0), 0.0)

    return top1_medication_id, round(top1_confidence, 4)


def _evaluate_record(record: dict[str, Any]) -> dict[str, Any]:
    sample_id = str(record.get("sample_id", "")).strip()
    created_at = str(record.get("created_at", "")).strip()
    original_image_path = str(record.get("original_image_path", "")).strip()

    success = bool(record.get("success", False))
    error_code = str(record.get("error_code", "")).strip() or None
    detection_boxes = record.get("detection_boxes") if isinstance(record.get("detection_boxes"), list) else []

    candidates = _safe_candidates(record.get("predicted_candidates"))
    top1_medication_id, top1_confidence = _top1_info(record, candidates)
    margin = _calc_margin(candidates)

    reason_codes: list[str] = []

    if error_code in {"VISION_INTERNAL_ERROR", "VISION_TIMEOUT", "VISION_UPSTREAM_ERROR"}:
        reason_codes.append(error_code)
    if error_code == "NO_PILL_DETECTED":
        reason_codes.append("NO_PILL_DETECTED")
    if error_code == "LOW_CONFIDENCE":
        reason_codes.append("LOW_CONFIDENCE")

    if not success and not reason_codes:
        reason_codes.append("UNKNOWN_FAILURE")

    if success:
        if top1_medication_id == "UNKNOWN_PILL":
            reason_codes.append("UNKNOWN_PILL")
        if top1_confidence < 0.90:
            reason_codes.append("BORDERLINE_CONFIDENCE")
        if margin is not None and margin < 0.15:
            reason_codes.append("LOW_MARGIN")

    # 복수 사유 허용 + 순서 보존 중복 제거
    deduped_reasons = list(dict.fromkeys(reason_codes))

    if not deduped_reasons:
        priority = "P4"
    else:
        priority = min(
            (REASON_TO_PRIORITY.get(reason, "P4") for reason in deduped_reasons), key=lambda p: PRIORITY_ORDER[p]
        )

    return {
        "sample_id": sample_id,
        "created_at": created_at,
        "original_image_path": original_image_path,
        "success": success,
        "error_code": error_code,
        "top1_medication_id": top1_medication_id or None,
        "top1_confidence": top1_confidence,
        "predicted_candidates": candidates,
        "detection_boxes": detection_boxes,
        "confidence_margin": margin,
        "review_priority": priority,
        "review_reason_codes": deduped_reasons,
        "review_status": "pending",
    }


def _load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line_no, line in enumerate(fp, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            evaluated = _evaluate_record(payload)
            # created_at 누락 시 입력 순서 보존을 위해 line_no 보조키 추가
            evaluated["_line_no"] = line_no
            records.append(evaluated)
    return records


def _sort_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda r: (
            PRIORITY_ORDER.get(str(r.get("review_priority", "P4")), 4),
            str(r.get("created_at", "")),
            int(r.get("_line_no", 0)),
        ),
        reverse=False,
    )


def _write_queue(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for record in records:
            record.pop("_line_no", None)
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review queue from vision records.jsonl")
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT, help="Input records.jsonl path")
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT, help="Output review_queue.jsonl path")
    parser.add_argument("--include-p4", action="store_true", help="Include P4 records (default: excluded)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[ERROR] input not found: {args.input}")
        return 1

    records = _load_records(args.input)
    records = _sort_records(records)

    if not args.include_p4:
        records = [r for r in records if r.get("review_priority") in {"P0", "P1", "P2", "P3"}]

    _write_queue(args.output, records)

    counts = {k: 0 for k in ["P0", "P1", "P2", "P3", "P4"]}
    for r in records:
        p = str(r.get("review_priority", "P4"))
        counts[p] = counts.get(p, 0) + 1

    print(f"[OK] wrote review queue: {args.output}")
    print(
        f"[OK] total={len(records)} P0={counts.get('P0', 0)} P1={counts.get('P1', 0)} P2={counts.get('P2', 0)} P3={counts.get('P3', 0)} P4={counts.get('P4', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
