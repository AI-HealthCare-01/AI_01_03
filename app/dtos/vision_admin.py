from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.dtos.base import BaseSerializerModel

ReviewPriorityValue = Literal["P0", "P1", "P2", "P3", "P4"]
QueueStatusValue = Literal["pending", "in_progress", "done"]
ReviewStatusValue = Literal["approved", "rejected", "needs_info"]
RetrainBucketValue = Literal["detect", "classify", "both", "none"]


class VisionAdminReviewQueueItem(BaseSerializerModel):
    sample_id: str
    review_priority: ReviewPriorityValue
    review_status: QueueStatusValue
    review_reason_codes: list[str] = Field(default_factory=list)
    error_code: str | None = None
    top1_medication_id: str | None = None
    top1_confidence: float | None = None
    original_image_path: str | None = None
    created_at: datetime

    @field_validator("top1_confidence")
    @classmethod
    def _round_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return round(float(value), 4)


class VisionAdminReviewQueueResponse(BaseSerializerModel):
    items: list[VisionAdminReviewQueueItem]
    total: int = Field(ge=0)


class VisionAdminSamplePayload(BaseSerializerModel):
    sample_id: str
    request_endpoint: str
    source_type: str
    original_image_path: str | None = None
    content_type: str | None = None
    image_size_bytes: int
    success: bool
    error_code: str | None = None
    predicted_candidates: list[dict[str, Any]] = Field(default_factory=list)
    top1_medication_id: str | None = None
    top1_confidence: float | None = None
    detection_boxes: list[list[int]] = Field(default_factory=list)
    raw_detections: list[dict[str, Any]] = Field(default_factory=list)
    model_version_detect: str | None = None
    model_version_classify: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("top1_confidence")
    @classmethod
    def _round_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return round(float(value), 4)


class VisionAdminReviewQueuePayload(BaseSerializerModel):
    sample_id: str
    review_priority: ReviewPriorityValue
    review_status: QueueStatusValue
    review_reason_codes: list[str] = Field(default_factory=list)
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class VisionAdminReviewResultPayload(BaseSerializerModel):
    sample_id: str
    review_status: ReviewStatusValue
    ground_truth_medication_id: str | None = None
    retrain_eligible: bool
    retrain_bucket: RetrainBucketValue
    reviewer: str
    reviewed_at: datetime
    decision_reason_codes: list[str] = Field(default_factory=list)
    queue_reason_codes: list[str] = Field(default_factory=list)
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime


class VisionAdminSampleDetailResponse(BaseSerializerModel):
    sample: VisionAdminSamplePayload
    queue: VisionAdminReviewQueuePayload | None = None
    review_result: VisionAdminReviewResultPayload | None = None


class VisionAdminReviewResultUpsertRequest(BaseSerializerModel):
    review_status: ReviewStatusValue
    ground_truth_medication_id: str | None = None
    retrain_eligible: bool
    retrain_bucket: RetrainBucketValue
    decision_reason_codes: list[str] = Field(default_factory=list)
    review_note: str | None = None

    @field_validator("decision_reason_codes")
    @classmethod
    def _normalize_reason_codes(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return list(dict.fromkeys(normalized))


class VisionAdminReviewResultUpsertResponse(BaseSerializerModel):
    sample_id: str
    review_status: ReviewStatusValue
    retrain_eligible: bool
    retrain_bucket: RetrainBucketValue
    reviewed_at: datetime

