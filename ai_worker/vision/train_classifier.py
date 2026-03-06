from __future__ import annotations

import argparse
import json
from pathlib import Path

from ultralytics import YOLO


def _find_class_names(data_dir: Path) -> list[str]:
    train_dir = data_dir / "train"
    if not train_dir.exists():
        raise FileNotFoundError(f"train directory not found: {train_dir}")
    return sorted([directory.name for directory in train_dir.iterdir() if directory.is_dir()])


def run_training(args: argparse.Namespace) -> Path:
    data_dir = args.data.resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"dataset not found: {data_dir}")

    class_names = _find_class_names(data_dir)
    if len(class_names) < 2:
        raise ValueError("classification fine-tuning requires at least 2 classes")

    print(f"[INFO] data={data_dir}")
    print(f"[INFO] classes={len(class_names)}")
    print(f"[INFO] model={args.model}")

    model = YOLO(args.model)
    results = model.train(
        data=str(data_dir),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        lr0=args.lr0,
        patience=args.patience,
        workers=args.workers,
        device=args.device,
        project=args.project,
        name=args.name,
        pretrained=True,
        cache=args.cache,
    )

    save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.name))
    weights_dir = save_dir / "weights"
    best_pt = weights_dir / "best.pt"
    last_pt = weights_dir / "last.pt"
    best_or_last = best_pt if best_pt.exists() else last_pt

    label_path = save_dir / "labels.json"
    label_path.write_text(json.dumps(class_names, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] save_dir={save_dir.resolve()}")
    print(f"[DONE] best_or_last={best_or_last.resolve() if best_or_last.exists() else 'NOT_FOUND'}")
    print(f"[DONE] labels={label_path.resolve()}")

    return best_or_last


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO classification fine-tuning")
    parser.add_argument("--data", type=Path, default=Path("./cls_data"))
    parser.add_argument("--model", type=str, default="yolo11n-cls.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--lr0", type=float, default=0.01)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--project", type=str, default="runs/classify")
    parser.add_argument("--name", type=str, default="pill_cls_finetune")
    parser.add_argument("--cache", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run_training(parse_args())
