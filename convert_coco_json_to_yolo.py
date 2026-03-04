import glob
import json
import os
from pathlib import Path


def ensure_dir(p: str):
    Path(p).mkdir(parents=True, exist_ok=True)


def coco_bbox_to_yolo(bbox, img_w, img_h):
    # bbox = [x_min, y_min, w, h] in pixels
    x, y, w, h = bbox
    x_c = x + w / 2.0
    y_c = y + h / 2.0
    # normalize to 0~1
    return (x_c / img_w, y_c / img_h, w / img_w, h / img_h)


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build_class_map_from_categories(categories):
    """
    categories: list of {"id": int, "name": str, ...}
    returns:
      catid_to_classidx: dict[int,int]
      classidx_to_name: list[str]
    """
    # 안정적으로 category id 오름차순으로 정렬해서 class index 부여
    cats_sorted = sorted(categories, key=lambda c: int(c["id"]))
    classidx_to_name = [c["name"] for c in cats_sorted]
    catid_to_classidx = {int(c["id"]): i for i, c in enumerate(cats_sorted)}
    return catid_to_classidx, classidx_to_name


def convert_split(json_dir, out_label_dir):
    ensure_dir(out_label_dir)

    json_files = sorted(glob.glob(os.path.join(json_dir, "*.json")))
    if not json_files:
        raise RuntimeError(f"No json files found in {json_dir}")

    global_class_names = None
    global_catid_to_idx = None

    for jp in json_files:
        d = load_json(jp)

        # categories → class mapping
        catid_to_idx, class_names = build_class_map_from_categories(d["categories"])
        if global_class_names is None:
            global_class_names = class_names
            global_catid_to_idx = catid_to_idx
        else:
            # 혹시 json마다 categories 순서/구성이 달라지면 바로 터뜨려서 잡게 함
            if class_names != global_class_names:
                raise RuntimeError(
                    f"Category list mismatch!\nFirst: {global_class_names}\nThis:  {class_names}\nFile: {jp}"
                )

        # image meta
        img_meta = d["images"][0]
        img_w = img_meta.get("width")
        img_h = img_meta.get("height")
        if img_w is None or img_h is None:
            raise RuntimeError(f"Missing width/height in images[0] for {jp}")

        # annotations → yolo lines
        lines = []
        for ann in d.get("annotations", []):
            bbox = ann.get("bbox")
            cat_id = int(ann.get("category_id"))
            if bbox is None:
                continue
            cls = global_catid_to_idx[cat_id]
            x, y, w, h = coco_bbox_to_yolo(bbox, img_w, img_h)

            # YOLO는 0~1 범위가 정상. 살짝 튀는 값은 clamp
            def clamp(v):
                return max(0.0, min(1.0, float(v)))

            x, y, w, h = map(clamp, (x, y, w, h))

            # 너무 작은/이상한 박스 제거(필요하면 조절 가능)
            if w <= 0 or h <= 0:
                continue

            lines.append(f"{cls} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")

        # output txt name = json basename
        base = os.path.splitext(os.path.basename(jp))[0]
        out_txt = os.path.join(out_label_dir, base + ".txt")

        with open(out_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

    return global_class_names


def write_dataset_yaml(class_names, out_path="dataset.yaml"):
    # YOLOv8 Ultralytics 형식
    content = []
    content.append("path: dataset")
    content.append("train: images/train")
    content.append("val: images/val")
    content.append("")
    content.append("names:")
    for i, name in enumerate(class_names):
        content.append(f"  {i}: {name}")
    Path(out_path).write_text("\n".join(content) + "\n", encoding="utf-8")


if __name__ == "__main__":
    train_json = "dataset/labels_json/train"
    val_json = "dataset/labels_json/val"
    train_out = "dataset/labels/train"
    val_out = "dataset/labels/val"

    # train 변환
    class_names = convert_split(train_json, train_out)

    # val 변환 (categories 불일치하면 여기서 에러로 잡힘)
    _ = convert_split(val_json, val_out)

    # dataset.yaml 생성
    write_dataset_yaml(class_names, out_path="dataset.yaml")

    print("✅ Done")
    print(f"- train txt: {train_out}")
    print(f"- val txt:   {val_out}")
    print("- dataset.yaml created")
    print(f"- classes ({len(class_names)}): {class_names[:10]}{'...' if len(class_names) > 10 else ''}")
