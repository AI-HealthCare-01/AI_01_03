from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.dtos.integration import OCRMedication
from app.services.prescription_flow import PrescriptionFlowService


def test_extract_frequency_and_days_from_dose_text():
    service = PrescriptionFlowService()

    frequency, days = service._extract_frequency_and_days("1일 3회, 5일분")

    assert frequency == 3
    assert days == 5


def test_extract_frequency_and_days_default_when_unmatched():
    service = PrescriptionFlowService()

    frequency, days = service._extract_frequency_and_days("복용법 확인 필요")

    assert frequency == 3
    assert days == 1


def test_resolve_schedule_times_uses_default_slots():
    service = PrescriptionFlowService()

    schedule_times = service._resolve_schedule_times(2)

    assert schedule_times == [time(8, 0), time(12, 0)]


@pytest.mark.asyncio
async def test_save_prescription_with_schedules_passes_same_transaction_connection(monkeypatch):
    service = PrescriptionFlowService()
    tx_conn = object()

    class _Tx:
        async def __aenter__(self):
            return tx_conn

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    prescription_create = AsyncMock(return_value=SimpleNamespace(id=10))
    item_create = AsyncMock(return_value=SimpleNamespace(id=20))
    create_schedules = AsyncMock(return_value=9)

    monkeypatch.setattr("app.services.prescription_flow.in_transaction", lambda: _Tx())
    monkeypatch.setattr("app.services.prescription_flow.Prescription.create", prescription_create)
    monkeypatch.setattr("app.services.prescription_flow.PrescriptionItem.create", item_create)
    monkeypatch.setattr(service, "_create_schedules_from_dose", create_schedules)

    result = await service.save_prescription_with_schedules(
        user_id=1,
        source_text="타이레놀정 1일 3회, 3일분",
        medications=[OCRMedication(name="타이레놀정", dose_text="1일 3회, 3일분")],
    )

    assert result == {"prescription_id": 10, "item_count": 1, "schedule_count": 9}
    prescription_create.assert_awaited_once()
    item_create.assert_awaited_once()
    create_schedules.assert_awaited_once()
    assert prescription_create.await_args.kwargs["using_db"] is tx_conn
    assert item_create.await_args.kwargs["using_db"] is tx_conn
    assert create_schedules.await_args.kwargs["connection"] is tx_conn


@pytest.mark.asyncio
async def test_save_prescription_with_schedules_propagates_schedule_error(monkeypatch):
    service = PrescriptionFlowService()

    class _Tx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    monkeypatch.setattr("app.services.prescription_flow.in_transaction", lambda: _Tx())
    monkeypatch.setattr(
        "app.services.prescription_flow.Prescription.create",
        AsyncMock(return_value=SimpleNamespace(id=11)),
    )
    monkeypatch.setattr(
        "app.services.prescription_flow.PrescriptionItem.create",
        AsyncMock(return_value=SimpleNamespace(id=21)),
    )

    async def _raise(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("schedule failed")

    monkeypatch.setattr(service, "_create_schedules_from_dose", _raise)

    with pytest.raises(RuntimeError, match="schedule failed"):
        await service.save_prescription_with_schedules(
            user_id=1,
            source_text="게보린정 1일 2회, 2일분",
            medications=[OCRMedication(name="게보린정", dose_text="1일 2회, 2일분")],
        )
