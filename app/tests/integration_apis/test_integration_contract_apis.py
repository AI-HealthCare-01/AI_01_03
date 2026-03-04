from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.prescriptions import Prescription, PrescriptionItem
from app.models.schedules import MedicationSchedule
from app.models.users import Gender, User


class TestIntegrationContractAPIs(TestCase):
    async def test_vision_identify_success_shape(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/vision/identify", json={})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True
        assert body["error_code"] is None
        assert isinstance(body["candidates"], list)
        assert body["candidates"]
        assert set(body["candidates"][0].keys()) == {"medication_id", "confidence"}

    async def test_vision_identify_low_confidence(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/vision/identify", json={"confidence": 0.2})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": False, "candidates": [], "error_code": "LOW_CONFIDENCE"}

    async def test_ocr_parse_failure_shape(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/ocr/parse", json={"mock_error_code": "PARSE_FAILED"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": False, "parsed": None, "error_code": "PARSE_FAILED"}

    async def test_ocr_parse_success_shape(self):
        payload = {"text": "타이레놀정 1일 3회, 3일분"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/ocr/parse", json=payload)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True
        assert body["error_code"] is None
        assert isinstance(body["parsed"]["medications"], list)
        assert body["parsed"]["medications"][0]["dose_text"] == "1일 3회, 3일분"

    async def test_ocr_parse_failure_when_input_missing(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/ocr/parse", json={})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": False, "parsed": None, "error_code": "PARSE_FAILED"}

    async def test_ocr_parse_failure_when_image_url_is_not_http(self):
        payload = {"image_url": "file:///tmp/prescription.png"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/ocr/parse", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": False, "parsed": None, "error_code": "PARSE_FAILED"}

    async def test_ocr_parse_prefers_text_when_text_and_image_url_are_both_provided(self):
        payload = {"text": "타이레놀정 1일 3회, 3일분", "image_url": "https://example.com/rx.jpg"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/ocr/parse", json=payload)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True
        assert body["error_code"] is None
        assert body["parsed"]["medications"][0]["name"] == "타이레놀정"
        assert body["parsed"]["medications"][0]["dose_text"] == "1일 3회, 3일분"

    async def test_ocr_parse_db_save_requires_user_id(self):
        payload = {"text": "타이레놀정 1일 3회, 3일분", "save_to_db": True}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/ocr/parse", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": False, "parsed": None, "error_code": "OCR_DB_SAVE_FAILED"}

    async def test_chat_success_has_disclaimer(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat", json={"rag_confidence": 0.9})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True
        assert "disclaimer" in body
        assert body["disclaimer"]
        assert "tts_segments" in body
        assert isinstance(body["tts_segments"], list)

    async def test_chat_low_rag_confidence(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat", json={"rag_confidence": 0.1})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"success": False, "error_code": "LOW_RAG_CONFIDENCE"}

    async def test_medication_history_success_shape(self):
        user = await User.create(
            email="history@test.com",
            hashed_password="hashed",
            name="tester",
            gender=Gender.MALE,
            birthday="2000-01-01",
            phone_number="01011112222",
        )
        prescription = await Prescription.create(user_id=user.id, source_text="rx")
        item = await PrescriptionItem.create(
            prescription_id=prescription.id,
            name="타이레놀정",
            dose_text="1일 3회, 3일분",
            medication_id="TYLENOL_500",
        )
        await MedicationSchedule.create(
            user_id=user.id,
            prescription_item_id=item.id,
            day_offset=0,
            time_slot="아침",
            scheduled_time="08:00:00",
            is_completed=True,
        )
        await MedicationSchedule.create(
            user_id=user.id,
            prescription_item_id=item.id,
            day_offset=0,
            time_slot="점심",
            scheduled_time="12:00:00",
            is_completed=False,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/history?user_id={user.id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True
        assert body["error_code"] is None
        assert body["data"]["total_count"] == 2
        assert body["data"]["completed_count"] == 1
        assert body["data"]["pending_count"] == 1
        assert len(body["data"]["items"]) == 2

    async def test_medication_dashboard_success_shape(self):
        user = await User.create(
            email="dashboard@test.com",
            hashed_password="hashed",
            name="tester2",
            gender=Gender.FEMALE,
            birthday="2001-01-01",
            phone_number="01033334444",
        )
        prescription = await Prescription.create(user_id=user.id, source_text="rx")
        item = await PrescriptionItem.create(
            prescription_id=prescription.id,
            name="게보린정",
            dose_text="1일 2회, 2일분",
            medication_id="GEBORIN_500",
        )
        await MedicationSchedule.create(
            user_id=user.id,
            prescription_item_id=item.id,
            day_offset=0,
            time_slot="아침",
            scheduled_time="08:00:00",
            is_completed=True,
        )
        await MedicationSchedule.create(
            user_id=user.id,
            prescription_item_id=item.id,
            day_offset=0,
            time_slot="저녁",
            scheduled_time="20:00:00",
            is_completed=False,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/dashboard?user_id={user.id}")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["success"] is True
        assert body["error_code"] is None
        assert body["data"]["total_schedules"] == 2
        assert body["data"]["completed_schedules"] == 1
        assert body["data"]["upcoming_schedules"] == 1
        assert body["data"]["adherence_rate"] == 50.0
