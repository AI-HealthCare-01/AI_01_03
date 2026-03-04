from app.services.ocr import OCRService


def test_parse_prescription_text_extracts_name_and_dose():
    service = OCRService()
    text = "타이레놀정 1일 3회, 3일분"

    medications = service.parse_prescription_text(text)

    assert len(medications) == 1
    assert medications[0].name == "타이레놀정"
    assert medications[0].dose_text == "1일 3회, 3일분"


def test_parse_prescription_text_uses_previous_line_as_name():
    service = OCRService()
    text = "타미플루캡슐\n1일 2회, 5일분"

    medications = service.parse_prescription_text(text)

    assert len(medications) == 1
    assert medications[0].name == "타미플루캡슐"
    assert medications[0].dose_text == "1일 2회, 5일분"

