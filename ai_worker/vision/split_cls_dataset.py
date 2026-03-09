from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def split_cls_dataset(src: Path, dst: Path, train_ratio: float, seed: int) -> None:
    random.seed(seed)

    train_root = dst / "train"
    val_root = dst / "val"
    train_root.mkdir(parents=True, exist_ok=True)
    val_root.mkdir(parents=True, exist_ok=True)

    classes = [directory for directory in src.iterdir() if directory.is_dir()]
    print(f"[INFO] src={src.resolve()}")
    print(f"[INFO] classes={len(classes)}")

    total_train = 0
    total_val = 0

    for cls_dir in classes:
        cls_name = cls_dir.name
        files = sorted([path for path in cls_dir.glob("*.png")])
        if not files:
            continue

        random.shuffle(files)
        n_train = int(len(files) * train_ratio)
        n_train = max(1, n_train) if len(files) > 1 else 1

        train_files = files[:n_train]
        val_files = files[n_train:]

        (train_root / cls_name).mkdir(parents=True, exist_ok=True)
        (val_root / cls_name).mkdir(parents=True, exist_ok=True)

        for image_path in train_files:
            shutil.copy2(image_path, train_root / cls_name / image_path.name)
        for image_path in val_files:
            shutil.copy2(image_path, val_root / cls_name / image_path.name)

        total_train += len(train_files)
        total_val += len(val_files)

        print(f"[CLASS {cls_name}] total={len(files)} train={len(train_files)} val={len(val_files)}")

    print(f"[DONE] train={total_train}, val={total_val}")
    print(f"[OUT] {dst.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="분류 데이터셋 train/val 분할")
    parser.add_argument("--src", type=Path, default=Path("./cls_dataset_itemseq"))
    parser.add_argument("--dst", type=Path, default=Path("./cls_data"))
    parser.add_argument("--train-ratio", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    split_cls_dataset(src=args.src, dst=args.dst, train_ratio=args.train_ratio, seed=args.seed)
