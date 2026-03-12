#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build class-wise image directories from manifest JSONL")
    parser.add_argument("--manifest", type=Path, required=True, help="Input manifest_classify.jsonl path")
    parser.add_argument("--out-src", type=Path, required=True, help="Output source root for class directories")
    parser.add_argument(
        "--mode",
        choices=["copy", "symlink"],
        default="copy",
        help="How to materialize image files (default: copy)",
    )
    parser.add_argument("--strict", action="store_true", help="Treat skipped records as errors")
    parser.add_argument("--limit", type=int, default=0, help="Optional max records to process (0 means all)")
    return parser.parse_args()


def _load_manifest(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    records: list[dict] = []
    with manifest_path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception as exc:
                raise ValueError(f"invalid json at line {line_no}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"manifest line {line_no} is not a JSON object")
            records.append(payload)
    return records


def _sanitize_class_label(class_label: str) -> str:
    raw = (class_label or "").strip()
    if not raw:
        return ""

    safe_chars: list[str] = []
    for char in raw:
        if char.isalnum() or char in {"-", "_"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")

    safe = "".join(safe_chars).strip("._- ")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe


def _resolve_output_path(out_src: Path, class_label: str, sample_id: str, image_path: Path) -> Path:
    file_name = image_path.name or "image"
    return out_src / class_label / f"{sample_id}__{file_name}"


def _materialize_image(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()

    if mode == "copy":
        shutil.copy2(src, dst)
        return
    if mode == "symlink":
        dst.symlink_to(src.resolve())
        return

    raise ValueError(f"unsupported mode: {mode}")


def _build_class_dirs(records: list[dict], out_src: Path, mode: str, strict: bool, limit: int) -> dict[str, int]:
    stats: dict[str, int] = {
        "total_records": len(records),
        "processed": 0,
        "written": 0,
        "skipped_missing_fields": 0,
        "skipped_missing_image": 0,
        "skipped_invalid_class_label": 0,
        "skipped_duplicate_sample_id": 0,
        "errors": 0,
    }

    selected = records[:limit] if limit and limit > 0 else records
    seen_sample_ids: set[str] = set()

    for row in selected:
        stats["processed"] += 1

        sample_id = str(row.get("sample_id", "")).strip()
        image_path_raw = str(row.get("image_path", "")).strip()
        class_label_raw = str(row.get("class_label", "")).strip()

        if not sample_id or not image_path_raw or not class_label_raw:
            stats["skipped_missing_fields"] += 1
            if strict:
                stats["errors"] += 1
            continue

        if sample_id in seen_sample_ids:
            stats["skipped_duplicate_sample_id"] += 1
            if strict:
                stats["errors"] += 1
            continue
        seen_sample_ids.add(sample_id)

        class_label = _sanitize_class_label(class_label_raw)
        if not class_label:
            stats["skipped_invalid_class_label"] += 1
            if strict:
                stats["errors"] += 1
            continue

        src = Path(image_path_raw).expanduser()
        if not src.exists() or not src.is_file():
            stats["skipped_missing_image"] += 1
            if strict:
                stats["errors"] += 1
            continue

        dst = _resolve_output_path(out_src=out_src, class_label=class_label, sample_id=sample_id, image_path=src)
        try:
            _materialize_image(src=src, dst=dst, mode=mode)
        except Exception:
            stats["errors"] += 1
            continue

        stats["written"] += 1

    return stats


def main() -> int:
    args = parse_args()
    try:
        records = _load_manifest(args.manifest)
        stats = _build_class_dirs(
            records=records,
            out_src=args.out_src,
            mode=args.mode,
            strict=args.strict,
            limit=args.limit,
        )

        print(f"[STAT] total_records={stats['total_records']}")
        print(f"[STAT] processed={stats['processed']}")
        print(f"[STAT] written={stats['written']}")
        print(f"[STAT] skipped_missing_fields={stats['skipped_missing_fields']}")
        print(f"[STAT] skipped_missing_image={stats['skipped_missing_image']}")
        print(f"[STAT] skipped_invalid_class_label={stats['skipped_invalid_class_label']}")
        print(f"[STAT] skipped_duplicate_sample_id={stats['skipped_duplicate_sample_id']}")
        print(f"[STAT] errors={stats['errors']}")
        print(f"[STAT] out_src={args.out_src}")

        return 1 if stats["errors"] > 0 else 0
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
