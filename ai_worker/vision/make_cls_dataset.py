from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from PIL import Image


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _resolve_class_name(image_meta: dict, class_key: Literal["item_seq", "drug_n", "dl_name"]) -> str | None:
    if class_key == "item_seq":
        item_seq = image_meta.get("item_seq")
        return str(item_seq) if item_seq else None
    if class_key == "drug_n":
        drug_n = image_meta.get("drug_N")
        return str(drug_n) if drug_n else None
    dl_name = image_meta.get("dl_name")
    if not dl_name:
        return None
    safe = "".join(char if char.isalnum() else "_" for char in str(dl_name)).strip("_")
    return safe or None


def _find_image_path(file_name: str, image_roots: list[Path], drug_code: str | None) -> Path | None:
    for root in image_roots:
        direct = root / file_name
        if direct.exists():
            return direct

        if drug_code:
            in_drug_dir = root / drug_code / file_name
            if in_drug_dir.exists():
                return in_drug_dir

    for root in image_roots:
        candidates = list(root.rglob(file_name))
        if candidates:
            return candidates[0]
    return None


def build_cls_dataset(
    *,
    image_roots: list[Path],
    json_root: Path,
    out_root: Path,
    class_key: Literal["item_seq", "drug_n", "dl_name"],
) -> None:
    out_root.mkdir(parents=True, exist_ok=True)

    json_files = sorted(json_root.rglob("*.json"))
    print(f"[INFO] json_root={json_root.resolve()}")
    print(f"[INFO] image_roots={[str(path.resolve()) for path in image_roots]}")
    print(f"[INFO] json_files={len(json_files)}")

    made = 0
    missing_img = 0
    bad_bbox = 0
    skipped = 0

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            continue

        images = data.get("images", [])
        annos = data.get("annotations", [])
        if not images or not annos:
            skipped += 1
            continue

        img_meta = images[0]
        file_name = img_meta.get("file_name")
        class_name = _resolve_class_name(img_meta, class_key=class_key)
        drug_code = str(img_meta.get("drug_N") or "").strip()

        if not file_name or not class_name:
            skipped += 1
            continue

        bbox = annos[0].get("bbox")
        if (not bbox) or len(bbox) != 4:
            bad_bbox += 1
            continue

        x, y, w, h = bbox
        img_path = _find_image_path(file_name=file_name, image_roots=image_roots, drug_code=drug_code)
        if img_path is None:
            missing_img += 1
            continue

        with Image.open(img_path) as image:
            image_width, image_height = image.size
            x1 = clamp(int(x), 0, image_width - 1)
            y1 = clamp(int(y), 0, image_height - 1)
            x2 = clamp(int(x + w), 1, image_width)
            y2 = clamp(int(y + h), 1, image_height)

            if x2 <= x1 or y2 <= y1:
                bad_bbox += 1
                continue

            crop = image.crop((x1, y1, x2, y2))

        out_dir = out_root / class_name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{jf.stem}.png"
        crop.save(out_path)
        made += 1

    print(f"[DONE] made={made}, missing_img={missing_img}, bad_bbox={bad_bbox}, skipped={skipped}")
    print(f"[OUT] {out_root.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="COCO JSON + bbox 기반 분류용 crop 데이터셋 생성")
    parser.add_argument("--img-root", type=Path, nargs="+", default=[Path("./dataset/images/train")])
    parser.add_argument("--json-root", type=Path, default=Path("./dataset/labels_json/train"))
    parser.add_argument("--out-root", type=Path, default=Path("./cls_dataset_itemseq"))
    parser.add_argument(
        "--class-key",
        choices=["item_seq", "drug_n", "dl_name"],
        default="item_seq",
        help="분류 라벨로 사용할 필드",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_cls_dataset(
        image_roots=[path for path in args.img_root],
        json_root=args.json_root,
        out_root=args.out_root,
        class_key=args.class_key,
    )
