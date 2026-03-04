from __future__ import annotations

import re
from datetime import time

from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.transactions import in_transaction

from app.dtos.integration import OCRMedication
from app.models.prescriptions import Prescription, PrescriptionItem
from app.models.schedules import MedicationSchedule

_DOSE_PATTERN = re.compile(r"(\d+)\s*일\s*(\d+)\s*회\s*,\s*(\d+)\s*일분")
_DEFAULT_SCHEDULE_TIMES = [
    time(8, 0),
    time(12, 0),
    time(18, 0),
    time(22, 0),
]


class PrescriptionFlowService:
    async def save_prescription_with_schedules(
        self,
        *,
        user_id: int,
        source_text: str,
        medications: list[OCRMedication],
    ) -> dict[str, int]:
        async with in_transaction() as connection:
            prescription = await Prescription.create(
                user_id=user_id,
                source_text=source_text,
                using_db=connection,
            )
            schedule_count = 0

            for medication in medications:
                item = await PrescriptionItem.create(
                    prescription_id=prescription.id,
                    name=medication.name,
                    dose_text=medication.dose_text,
                    using_db=connection,
                )

                created = await self._create_schedules_from_dose(
                    user_id=user_id,
                    prescription_item_id=item.id,
                    dose_text=medication.dose_text,
                    connection=connection,
                )
                schedule_count += created

        return {
            "prescription_id": int(prescription.id),
            "item_count": len(medications),
            "schedule_count": schedule_count,
        }

    async def _create_schedules_from_dose(
        self,
        *,
        user_id: int,
        prescription_item_id: int,
        dose_text: str,
        connection: BaseDBAsyncClient | None = None,
    ) -> int:
        frequency_per_day, duration_days = self._extract_frequency_and_days(dose_text)
        schedule_times = self._resolve_schedule_times(frequency_per_day)

        total_created = 0
        for day_offset in range(duration_days):
            for index, scheduled_time in enumerate(schedule_times):
                await MedicationSchedule.create(
                    user_id=user_id,
                    prescription_item_id=prescription_item_id,
                    day_offset=day_offset,
                    time_slot=f"DOSE_{index + 1}",
                    scheduled_time=scheduled_time,
                    using_db=connection,
                )
                total_created += 1
        return total_created

    def _extract_frequency_and_days(self, dose_text: str) -> tuple[int, int]:
        match = _DOSE_PATTERN.search(dose_text)
        if not match:
            return (3, 1)

        frequency_per_day = max(1, int(match.group(2)))
        duration_days = max(1, int(match.group(3)))
        return (frequency_per_day, duration_days)

    def _resolve_schedule_times(self, frequency_per_day: int) -> list[time]:
        if frequency_per_day <= len(_DEFAULT_SCHEDULE_TIMES):
            return _DEFAULT_SCHEDULE_TIMES[:frequency_per_day]

        base_times = _DEFAULT_SCHEDULE_TIMES[:]
        while len(base_times) < frequency_per_day:
            base_times.append(_DEFAULT_SCHEDULE_TIMES[-1])
        return base_times
