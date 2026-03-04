import json
from pathlib import Path

from PIL import Image

IMG_ROOT = Path("./dataset/images/train")
JSON_ROOT = Path("./dataset/labels_json/train")
OUT_ROOT = Path("./cls_dataset_itemseq")  # 결과: item_seq 폴더로 저장

OUT_ROOT.mkdir(parents=True, exist_ok=True)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


json_files = sorted(JSON_ROOT.glob("*.json"))
print(f"[INFO] JSON files: {len(json_files)}")

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
    item_seq = img_meta.get("item_seq")

    if not file_name or item_seq is None:
        skipped += 1
        continue

    bbox = annos[0].get("bbox")
    if (not bbox) or len(bbox) != 4:
        bad_bbox += 1
        continue

    x, y, w, h = bbox
    img_path = IMG_ROOT / file_name
    if not img_path.exists():
        missing_img += 1
        continue

    with Image.open(img_path) as im:
        W, H = im.size
        x1 = clamp(int(x), 0, W - 1)
        y1 = clamp(int(y), 0, H - 1)
        x2 = clamp(int(x + w), 1, W)
        y2 = clamp(int(y + h), 1, H)

        if x2 <= x1 or y2 <= y1:
            bad_bbox += 1
            continue

        crop = im.crop((x1, y1, x2, y2))

    out_dir = OUT_ROOT / str(item_seq)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 파일명 충돌 방지: json 파일 stem 사용
    out_path = out_dir / f"{jf.stem}.png"
    crop.save(out_path)
    made += 1

print(f"[DONE] made={made}, missing_img={missing_img}, bad_bbox={bad_bbox}, skipped={skipped}")
print(f"[OUT]  {OUT_ROOT.resolve()}")
