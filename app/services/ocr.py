from __future__ import annotations

import re
import time
import uuid
from typing import Any

import httpx

from app.core import config
from app.dtos.integration import OCRMedication

_DOSE_REGEX = re.compile(r"(\d+\s*일\s*\d+\s*회\s*,\s*\d+\s*일분)")
_NAME_CLEANUP_REGEX = re.compile(r"[\-:()]+")


class OCRService:
    async def extract_text_from_image_url(self, image_url: str) -> str:
        if not config.OCR_INVOKE_URL or not config.OCR_SECRET_KEY:
            raise ValueError("OCR configuration is missing")

        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [
                {
                    "format": "jpg",
                    "name": "prescription",
                    "url": image_url,
                }
            ],
        }
        headers = {"X-OCR-SECRET": config.OCR_SECRET_KEY}

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(config.OCR_INVOKE_URL, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        return self._collect_infer_text(body)

    def parse_prescription_text(self, text: str) -> list[OCRMedication]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        medications: list[OCRMedication] = []

        previous_line = ""
        for line in lines:
            dose_match = _DOSE_REGEX.search(line)
            if not dose_match:
                previous_line = line
                continue

            dose_text = self._normalize_spaces(dose_match.group(1))
            name_candidate = line.replace(dose_match.group(1), "").strip(" ,")
            if not name_candidate:
                name_candidate = previous_line
            name = self._normalize_name(name_candidate)
            if not name:
                name = "확인필요"

            medications.append(OCRMedication(name=name, dose_text=dose_text))
            previous_line = line

        return medications

    def _collect_infer_text(self, payload: dict[str, Any]) -> str:
        images = payload.get("images")
        if not isinstance(images, list):
            return ""
        if not images:
            return ""

        fields = images[0].get("fields", [])
        if not isinstance(fields, list):
            return ""

        collected: list[str] = []
        for field in fields:
            if not isinstance(field, dict):
                continue
            infer_text = field.get("inferText")
            if isinstance(infer_text, str) and infer_text.strip():
                collected.append(infer_text.strip())
        return "\n".join(collected)

    def _normalize_name(self, name: str) -> str:
        return _NAME_CLEANUP_REGEX.sub(" ", name).strip()

    def _normalize_spaces(self, value: str) -> str:
        return " ".join(value.split())
