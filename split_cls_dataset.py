import random
import shutil
from pathlib import Path

SRC = Path("./cls_dataset_itemseq")
DST = Path("./cls_data")
TRAIN_RATIO = 0.9
SEED = 42

random.seed(SEED)

train_root = DST / "train"
val_root = DST / "val"
train_root.mkdir(parents=True, exist_ok=True)
val_root.mkdir(parents=True, exist_ok=True)

classes = [d for d in SRC.iterdir() if d.is_dir()]
print(f"[INFO] classes: {len(classes)}")

total_train = 0
total_val = 0

for cls_dir in classes:
    cls_name = cls_dir.name
    files = sorted([p for p in cls_dir.glob("*.png")])
    if not files:
        continue

    random.shuffle(files)
    n_train = int(len(files) * TRAIN_RATIO)

    train_files = files[:n_train]
    val_files = files[n_train:]

    (train_root / cls_name).mkdir(parents=True, exist_ok=True)
    (val_root / cls_name).mkdir(parents=True, exist_ok=True)

    for p in train_files:
        shutil.copy2(p, train_root / cls_name / p.name)
    for p in val_files:
        shutil.copy2(p, val_root / cls_name / p.name)

    total_train += len(train_files)
    total_val += len(val_files)

    print(f"[CLASS {cls_name}] total={len(files)} train={len(train_files)} val={len(val_files)}")

print(f"[DONE] train={total_train}, val={total_val}")
print(f"[OUT]  {DST.resolve()}")
