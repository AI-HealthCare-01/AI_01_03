from datetime import time

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

