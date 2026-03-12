from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.dtos.base import BaseSerializerModel

MEDICATION_ID_PATTERN = r"^[A-Z0-9]+(_[A-Z0-9]+)+$"


class ContractBaseResponse(BaseSerializerModel):
    success: bool
    error_code: str | None = None


class VisionIdentifyRequest(BaseModel):
    confidence: float | None = None
    medication_id: str | None = None
    mock_error_code: str | None = None


class VisionCandidate(BaseSerializerModel):
    medication_id: str = Field(pattern=MEDICATION_ID_PATTERN)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("confidence")
    @classmethod
    def _round_confidence(cls, v: float) -> float:
        return round(v, 4)


class VisionIdentifyResponse(ContractBaseResponse):
    candidates: list[VisionCandidate]


class VisionDetailRequest(BaseModel):
    medication_id: str = Field(pattern=MEDICATION_ID_PATTERN)
    drug_name_hint: str | None = None


class VisionDetailResponse(ContractBaseResponse):
    medication_id: str = Field(pattern=MEDICATION_ID_PATTERN)
    drug_name: str | None = None
    context_text: str | None = None


class OCRParseRequest(BaseModel):
    text: str | None = None
    image_url: str | None = None
    user_id: int | None = None
    save_to_db: bool = False
    mock_error_code: str | None = None


class OCRMedication(BaseSerializerModel):
    name: str
    dose_text: str


class OCRParsed(BaseSerializerModel):
    medications: list[OCRMedication]


class OCRParseResponse(ContractBaseResponse):
    parsed: OCRParsed | None


class ChatRequest(BaseModel):
    medication_id: str | None = None
    user_question: str | None = None
    rag_confidence: float | None = None
    mock_error_code: str | None = None


class Citation(BaseSerializerModel):
    source: str
    title: str


class ChatSections(BaseSerializerModel):
    summary: str = ""
    dosage: str = ""
    precautions: str = ""
    tips: str = ""


class ChatSuccessResponse(ContractBaseResponse):
    success: Literal[True] = True
    answer: str = ""
    sections: ChatSections = Field(default_factory=ChatSections)
    tts_segments: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    disclaimer: str = ""


class ChatFailureResponse(ContractBaseResponse):
    success: Literal[False] = False
    error_code: str


class MedicationHistoryItem(BaseSerializerModel):
    schedule_id: int
    medication_name: str
    dose_text: str
    day_offset: int
    time_slot: str
    scheduled_time: str
    is_completed: bool


class MedicationHistoryData(BaseSerializerModel):
    total_count: int
    completed_count: int
    pending_count: int
    items: list[MedicationHistoryItem]


class MedicationHistoryResponse(ContractBaseResponse):
    data: MedicationHistoryData


class MedicationDashboardData(BaseSerializerModel):
    total_schedules: int
    completed_schedules: int
    upcoming_schedules: int
    adherence_rate: float


class MedicationDashboardResponse(ContractBaseResponse):
    data: MedicationDashboardData
