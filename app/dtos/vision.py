from __future__ import annotations

from pydantic import Field, field_validator

from app.dtos.base import BaseSerializerModel


class VisionCandidate(BaseSerializerModel):
    drug_name: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, value: float) -> float:
        return round(value, 4)


class VisionDetection(BaseSerializerModel):
    bbox: list[int] = Field(min_length=4, max_length=4)
    candidates: list[VisionCandidate] = Field(default_factory=list)

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, value: list[int]) -> list[int]:
        if len(value) != 4:
            raise ValueError("bbox must include [x, y, w, h]")
        _, _, w, h = value
        if w <= 0 or h <= 0:
            raise ValueError("bbox width and height must be positive")
        return value


class VisionIdentifyResponse(BaseSerializerModel):
    detections: list[VisionDetection] = Field(default_factory=list)
    latency_ms: int = Field(ge=0)
    disclaimer: str


class VisionErrorResponse(BaseSerializerModel):
    error_code: str
    message: str
