from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as f
from PIL import Image
from torchvision import models, transforms

# ====== 경로(프로젝트 루트 기준) ======
# 가중치/매핑 파일을 어디에 둘지 팀 규칙에 맞춰 조정 가능
ASSET_DIR = Path("ai_worker/vision/assets")
WEIGHT_PATH = ASSET_DIR / "vision_resnet18_itemseq.pth"
CLASS_TO_IDX_PATH = ASSET_DIR / "class_to_idx.json"
ITEMSEQ_TO_MED_PATH = ASSET_DIR / "itemseq_to_medication_id.json"

# ====== 전처리 ======
_TF = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)


class VisionClassifier:
    """
    item_seq 분류 모델 래퍼
    - predict(image_path) -> (medication_id, confidence)
    """

    def __init__(self, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # class_to_idx
        class_to_idx: dict[str, int] = json.loads(CLASS_TO_IDX_PATH.read_text(encoding="utf-8"))
        self.idx_to_itemseq: dict[int, str] = {v: k for k, v in class_to_idx.items()}
        self.num_classes = len(self.idx_to_itemseq)

        # itemseq -> medication_id (없으면 ITEMSEQ_ 규칙으로 fallback)
        if ITEMSEQ_TO_MED_PATH.exists():
            self.itemseq_to_med: dict[str, str] = json.loads(ITEMSEQ_TO_MED_PATH.read_text(encoding="utf-8"))
        else:
            self.itemseq_to_med = {}

        # model
        self.model = models.resnet18(weights=None)
        self.model.fc = nn.Linear(self.model.fc.in_features, self.num_classes)

        state = torch.load(WEIGHT_PATH, map_location=self.device)
        self.model.load_state_dict(state)
        self.model.to(self.device)
        self.model.eval()

    def _itemseq_to_medication_id(self, item_seq: str) -> str:
        # Sprint01 계약: 영문대문자 + 언더스코어
        if item_seq in self.itemseq_to_med:
            return self.itemseq_to_med[item_seq]
        return f"ITEMSEQ_{item_seq}"

    @torch.no_grad()
    def predict(self, image_path: str) -> tuple[str, float]:
        img = Image.open(image_path).convert("RGB")
        x = _TF(img).unsqueeze(0).to(self.device)

        logits = self.model(x)
        probs = f.softmax(logits, dim=1)
        conf, pred = probs.max(dim=1)

        conf_f = float(conf.item())
        pred_idx = int(pred.item())
        item_seq = self.idx_to_itemseq[pred_idx]

        medication_id = self._itemseq_to_medication_id(item_seq)
        return medication_id, conf_f


# 싱글톤 (서버 뜰 때 1번만 로드하려고)
_classifier: VisionClassifier | None = None


def get_classifier() -> VisionClassifier:
    global _classifier
    if _classifier is None:
        _classifier = VisionClassifier()
    return _classifier
