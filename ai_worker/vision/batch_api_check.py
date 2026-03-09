from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

from app.main import app


def _list_images(root: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in exts]


def _expected_medication_id(path: Path) -> str:
    # Folder name is class label like K-040221 -> K_040221
    return path.parent.name.upper().replace("-", "_")


def _is_contract_success(body: dict[str, Any]) -> bool:
    if not isinstance(body, dict):
        return False
    if set(body.keys()) != {"success", "candidates", "error_code"}:
        return False
    if not isinstance(body.get("success"), bool):
        return False
    if not (isinstance(body.get("error_code"), str) or body.get("error_code") is None):
        return False
    if not isinstance(body.get("candidates"), list):
        return False
    for candidate in body["candidates"]:
        if not isinstance(candidate, dict):
            return False
        if set(candidate.keys()) != {"medication_id", "confidence"}:
            return False
        if not isinstance(candidate["medication_id"], str):
            return False
        if not isinstance(candidate["confidence"], (int, float)):
            return False
    return True


async def run_check(image_root: Path, limit: int, seed: int) -> dict[str, Any]:
    all_images = _list_images(image_root)
    rnd = random.Random(seed)
    rnd.shuffle(all_images)
    images = all_images[: max(1, min(limit, len(all_images)))]

    result: dict[str, Any] = {
        "total": len(images),
        "success_count": 0,
        "failure_count": 0,
        "contract_error_count": 0,
        "top1_match_count": 0,
        "avg_latency_ms": 0.0,
        "items": [],
    }

    total_latency = 0.0
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for image_path in images:
            expected = _expected_medication_id(image_path)
            started = time.perf_counter()
            with image_path.open("rb") as image_file:
                response = await client.post(
                    "/api/vision/identify",
                    files={"image": (image_path.name, image_file, "image/png")},
                )
            latency_ms = (time.perf_counter() - started) * 1000.0
            total_latency += latency_ms

            body = response.json()
            contract_ok = _is_contract_success(body)
            if not contract_ok:
                result["contract_error_count"] += 1

            top1 = None
            top1_conf = None
            if body.get("candidates"):
                top1 = body["candidates"][0]["medication_id"]
                top1_conf = body["candidates"][0]["confidence"]

            success = bool(body.get("success"))
            if success:
                result["success_count"] += 1
                if top1 == expected:
                    result["top1_match_count"] += 1
            else:
                result["failure_count"] += 1

            result["items"].append(
                {
                    "image": str(image_path),
                    "expected_medication_id": expected,
                    "status_code": response.status_code,
                    "success": success,
                    "error_code": body.get("error_code"),
                    "top1_medication_id": top1,
                    "top1_confidence": top1_conf,
                    "latency_ms": round(latency_ms, 2),
                    "contract_ok": contract_ok,
                }
            )

    if images:
        result["avg_latency_ms"] = round(total_latency / len(images), 2)
    if result["success_count"] > 0:
        result["top1_match_rate"] = round(result["top1_match_count"] / result["success_count"], 4)
    else:
        result["top1_match_rate"] = 0.0
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vision API 배치 계약/정확도 스모크 체크")
    parser.add_argument(
        "--image-root",
        type=Path,
        default=Path("runs/pill_cls/cls_data/val"),
        help="검증 이미지 루트 (클래스 폴더 구조)",
    )
    parser.add_argument("--limit", type=int, default=30, help="검증할 이미지 개수")
    parser.add_argument("--seed", type=int, default=42, help="샘플링 시드")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/reports/vision_api_batch_report.json"),
        help="리포트 저장 경로",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    report = asyncio.run(run_check(args.image_root, args.limit, args.seed))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] report: {args.out.resolve()}")
    print(
        "[SUMMARY] total={total} success={success} failure={failure} contract_error={contract_error} "
        "top1_match_rate={match_rate} avg_latency_ms={latency}".format(
            total=report["total"],
            success=report["success_count"],
            failure=report["failure_count"],
            contract_error=report["contract_error_count"],
            match_rate=report["top1_match_rate"],
            latency=report["avg_latency_ms"],
        )
    )
