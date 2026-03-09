from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.core import config
from app.dtos.vision import VisionCandidate
from app.services.vision import VisionService, VisionUpstreamError


def _make_jpeg_bytes(width: int = 120, height: int = 80) -> bytes:
    image = Image.new("RGB", (width, height), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_extract_candidates_normalizes_confidence_and_top_k():
    service = VisionService()
    payload = {
        "candidates": [
            {"drug_name": "A", "confidence": "95%"},
            {"drug_name": "B", "confidence": 0.63},
            {"drug_name": "A", "confidence": 0.72},
            {"drug_name": "C", "confidence": 42},
        ]
    }

    with patch.object(config, "VISION_TOP_K", 2):
        candidates = service._extract_candidates(payload)

    assert [candidate.drug_name for candidate in candidates] == ["A", "B"]
    assert [candidate.confidence for candidate in candidates] == [0.95, 0.63]


def test_detect_bboxes_uses_full_image_fallback_when_detector_empty():
    service = VisionService()
    image = Image.new("RGB", (100, 70), color="white")

    with (
        patch.object(service, "_detect_bboxes_with_yolo", return_value=[]),
        patch.object(config, "VISION_ENABLE_FULL_IMAGE_FALLBACK", True),
    ):
        bboxes = service._detect_bboxes(image)

    assert bboxes == [[0, 0, 100, 70]]


def test_merge_candidates_blends_overlap_and_keeps_new_classifier_labels():
    service = VisionService()
    openai_candidates = [
        VisionCandidate(drug_name="K-040221", confidence=0.7),
        VisionCandidate(drug_name="K-040330", confidence=0.4),
    ]
    classifier_candidates = [
        VisionCandidate(drug_name="K-040221", confidence=0.95),
        VisionCandidate(drug_name="K-040657", confidence=0.92),
    ]

    with (
        patch.object(config, "VISION_CLASSIFIER_WEIGHT", 0.7),
        patch.object(config, "VISION_TOP_K", 3),
    ):
        merged = service._merge_candidates(
            openai_candidates=openai_candidates,
            classifier_candidates=classifier_candidates,
        )

    assert [candidate.drug_name for candidate in merged] == ["K-040657", "K-040221", "K-040330"]
    assert merged[0].confidence == 0.92
    assert merged[1].confidence == 0.875


def test_predict_classifier_candidates_when_enabled(tmp_path):
    service = VisionService()
    dummy_weights = tmp_path / "best.pt"
    dummy_weights.write_bytes(b"dummy")
    image = Image.new("RGB", (100, 70), color="white")

    mock_outputs = [
        {"class_id": 0, "class_name": "K-040221", "confidence": 0.91},
        {"class_id": 1, "class_name": "K-040330", "confidence": 0.11},
    ]
    with (
        patch.object(config, "VISION_CLASSIFIER_ENABLED", True),
        patch.object(config, "VISION_CLASSIFIER_MODEL_PATH", str(dummy_weights)),
        patch.object(config, "VISION_CLASSIFIER_LABELS_PATH", ""),
        patch.object(config, "VISION_CLASSIFIER_TOP_K", 2),
        patch("ai_worker.vision.classifier.predict_classes", return_value=mock_outputs),
    ):
        candidates = service._predict_classifier_candidates(image)

    assert len(candidates) == 2
    assert candidates[0].drug_name == "K-040221"
    assert candidates[0].confidence == 0.91


@pytest.mark.asyncio
async def test_identify_builds_multi_object_response_with_limit():
    service = VisionService()
    base_image = Image.new("RGB", (200, 120), color="white")

    with (
        patch.object(service, "_load_image", return_value=base_image),
        patch.object(service, "_resize_image_if_needed", return_value=base_image),
        patch.object(service, "_detect_bboxes", return_value=[[0, 0, 100, 60], [20, 10, 80, 60], [50, 50, 40, 40]]),
        patch.object(
            service,
            "_identify_candidates",
            new=AsyncMock(
                side_effect=[
                    [VisionCandidate(drug_name="아스피린", confidence=0.91)],
                    [VisionCandidate(drug_name="타이레놀", confidence=0.82)],
                ]
            ),
        ),
        patch.object(config, "VISION_MAX_DETECTIONS", 2),
        patch.object(config, "VISION_DISCLAIMER", "본 서비스는 복약 보조 수단입니다."),
    ):
        response = await service.identify(image_bytes=_make_jpeg_bytes(), content_type="image/jpeg")

    assert len(response.detections) == 2
    assert response.detections[0].bbox == [0, 0, 100, 60]
    assert response.detections[0].candidates[0].drug_name == "아스피린"
    assert response.detections[1].candidates[0].drug_name == "타이레놀"
    assert response.disclaimer == "본 서비스는 복약 보조 수단입니다."
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_identify_candidates_fallbacks_to_classifier_when_openai_fails():
    service = VisionService()
    crop = Image.new("RGB", (120, 80), color="white")
    classifier_candidates = [VisionCandidate(drug_name="K-040221", confidence=0.91)]

    with (
        patch.object(service, "_encode_image_to_base64", return_value="dummy-base64"),
        patch.object(service, "_predict_classifier_candidates", return_value=classifier_candidates),
        patch.object(service, "_call_openai_with_retry", new=AsyncMock(side_effect=VisionUpstreamError())),
    ):
        candidates = await service._identify_candidates(crop)

    assert len(candidates) == 1
    assert candidates[0].drug_name == "K-040221"
    assert candidates[0].confidence == 0.91


@pytest.mark.asyncio
async def test_identify_candidates_skips_openai_when_key_missing_and_classifier_exists():
    service = VisionService()
    crop = Image.new("RGB", (120, 80), color="white")
    classifier_candidates = [VisionCandidate(drug_name="K-040221", confidence=0.9)]

    with (
        patch.object(config, "OPENAI_API_KEY", ""),
        patch.object(service, "_encode_image_to_base64", return_value="dummy-base64"),
        patch.object(service, "_predict_classifier_candidates", return_value=classifier_candidates),
        patch.object(service, "_call_openai_with_retry", new=AsyncMock()) as openai_call,
    ):
        candidates = await service._identify_candidates(crop)

    openai_call.assert_not_called()
    assert len(candidates) == 1
    assert candidates[0].drug_name == "K-040221"
