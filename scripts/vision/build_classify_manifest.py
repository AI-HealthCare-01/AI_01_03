#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from app.db.databases import TORTOISE_ORM

DEFAULT_OUT = Path("runs/vision_samples/manifest_classify.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build classify manifest from approved/retrain-eligible review data")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output manifest JSONL path (default: runs/vision_samples/manifest_classify.jsonl)",
    )
    parser.add_argument(
        "--require-image-exists",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip rows when image file does not exist (default: true)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max row count (0 means no limit)",
    )
    parser.add_argument(
        "--db-host",
        type=str,
        default=None,
        help="Optional DB host override (e.g. 127.0.0.1 for local runs)",
    )
    return parser.parse_args()


def _normalize_class_label(medication_id: str) -> str:
    value = (medication_id or "").strip()
    if value.startswith("K_"):
        return value.replace("K_", "K-", 1)
    return value


async def _fetch_candidate_rows(*, limit: int = 0) -> list[dict[str, Any]]:
    connection = Tortoise.get_connection("default")

    sql = """
    SELECT
        rr.sample_id AS sample_id,
        rr.ground_truth_medication_id AS ground_truth_medication_id,
        rr.reviewed_at AS reviewed_at,
        rr.retrain_bucket AS retrain_bucket,
        s.original_image_path AS original_image_path
    FROM vision_review_results rr
    INNER JOIN vision_samples s
        ON s.sample_id = rr.sample_id
    WHERE rr.review_status = 'approved'
      AND rr.retrain_eligible = 1
      AND rr.retrain_bucket IN ('classify', 'both')
      AND rr.ground_truth_medication_id IS NOT NULL
      AND rr.ground_truth_medication_id <> ''
      AND s.original_image_path IS NOT NULL
      AND s.original_image_path <> ''
    ORDER BY rr.reviewed_at DESC
    """

    if limit and limit > 0:
        sql += f" LIMIT {int(limit)}"

    rows = await connection.execute_query_dict(sql)
    return rows if isinstance(rows, list) else []


def _to_manifest_record(row: dict[str, Any]) -> dict[str, Any] | None:
    sample_id = str(row.get("sample_id", "")).strip()
    image_path = str(row.get("original_image_path", "")).strip()
    ground_truth_medication_id = str(row.get("ground_truth_medication_id", "")).strip()
    retrain_bucket = str(row.get("retrain_bucket", "")).strip()
    reviewed_at = row.get("reviewed_at")

    if not sample_id or not image_path or not ground_truth_medication_id:
        return None

    class_label = _normalize_class_label(ground_truth_medication_id)
    if not class_label:
        return None

    return {
        "sample_id": sample_id,
        "image_path": image_path,
        "ground_truth_medication_id": ground_truth_medication_id,
        "class_label": class_label,
        "reviewed_at": str(reviewed_at) if reviewed_at is not None else None,
        "retrain_bucket": retrain_bucket,
    }


def _write_jsonl(records: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_tortoise_config(db_host: str | None = None) -> dict[str, Any]:
    cfg = deepcopy(TORTOISE_ORM)
    if db_host:
        cfg["connections"]["default"]["credentials"]["host"] = db_host
    return cfg


async def _run(args: argparse.Namespace) -> int:
    primary_cfg = _build_tortoise_config(args.db_host)
    primary_host = str(primary_cfg["connections"]["default"]["credentials"]["host"]).strip()
    active_host = primary_host
    rows: list[dict[str, Any]]

    await Tortoise.init(config=primary_cfg)
    try:
        try:
            rows = await _fetch_candidate_rows(limit=args.limit)
        except Exception as exc:
            # Tortoise는 첫 쿼리 시점에 실제 연결을 시도할 수 있어, 여기서 연결 에러를 처리한다.
            retry_allowed = args.db_host is None and primary_host == "mysql"
            is_connect_error = isinstance(exc, DBConnectionError) or "can't connect to mysql server" in str(exc).lower()
            if not (retry_allowed and is_connect_error):
                raise

            fallback_host = "127.0.0.1"
            print(f"[WARN] DB host '{primary_host}' connection failed. retry with host={fallback_host}")
            await Tortoise.close_connections()
            await Tortoise.init(config=_build_tortoise_config(fallback_host))
            active_host = fallback_host
            rows = await _fetch_candidate_rows(limit=args.limit)

        written_records: list[dict[str, Any]] = []
        skipped = 0

        for row in rows:
            record = _to_manifest_record(row)
            if record is None:
                skipped += 1
                continue

            if args.require_image_exists and not Path(record["image_path"]).exists():
                skipped += 1
                continue

            written_records.append(record)

        _write_jsonl(written_records, args.out)

        print(f"[OK] db_host={active_host}")
        print(f"[OK] out={args.out}")
        print(f"[OK] written={len(written_records)} skipped={skipped}")
        return 0
    finally:
        await Tortoise.close_connections()


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(_run(args))
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
