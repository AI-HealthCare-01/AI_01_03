# Pill Vision Fine-tuning

## 1) COCO bbox -> 분류용 crop 생성

```bash
python -m ai_worker.vision.make_cls_dataset \
  --img-root ./dataset/images/train \
  --json-root ./dataset/labels_json/train \
  --out-root ./cls_dataset_itemseq
```

## 2) train/val 분할

```bash
python -m ai_worker.vision.split_cls_dataset \
  --src ./cls_dataset_itemseq \
  --dst ./cls_data \
  --train-ratio 0.9 \
  --seed 42
```

## 3) YOLO 분류모델 파인튜닝

```bash
python -m ai_worker.vision.train_classifier \
  --data ./cls_data \
  --model yolo11n-cls.pt \
  --epochs 30 \
  --imgsz 224 \
  --batch 64 \
  --device cpu \
  --project runs/classify \
  --name pill_cls_finetune
```

학습 결과:
- `runs/classify/pill_cls_finetune/weights/best.pt`
- `runs/classify/pill_cls_finetune/labels.json`

## 4) 추론 확인

```bash
python -m ai_worker.vision.predict_classifier \
  --weights runs/classify/pill_cls_finetune/weights/best.pt \
  --image ./some_pill.jpg \
  --topk 3
```

## 5) medication_id 매핑 템플릿 생성

```bash
python -m ai_worker.vision.build_medication_map_template \
  --labels runs/classify/pill_cls_finetune/labels.json \
  --fill-identity \
  --out app/resources/vision_medication_map.json
```

## 6) Vision API 배치 스모크 체크

```bash
python -m ai_worker.vision.batch_api_check \
  --image-root runs/pill_cls/cls_data/val \
  --limit 30 \
  --out runs/reports/vision_api_batch_report.json
```
