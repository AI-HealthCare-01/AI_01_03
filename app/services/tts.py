import asyncio
import re
from io import BytesIO

from gtts import gTTS

# 고유 한국어 수사 (하나, 둘, 셋 ...)
_NATIVE_KO = {
    1: "한",
    2: "두",
    3: "세",
    4: "네",
    5: "다섯",
    6: "여섯",
    7: "일곱",
    8: "여덟",
    9: "아홉",
    10: "열",
}

# 단위 앞 숫자를 고유어로 읽는 패턴 (예: 1정→한 정, 3회→세 번)
_UNIT_MAP = {
    "정": "정",
    "알": "알",
    "캡슐": "캡슐",
    "포": "포",
    "회": "번",
    "번": "번",
    "개": "개",
    "잔": "잔",
    "시": "시",
    "시간": "시간",
    "가지": "가지",
    "종": "종",
    "종류": "종류",
}


def _native_num(n: int) -> str:
    """1~99 를 고유 한국어 수사로 변환."""
    if n <= 0 or n > 99:
        return str(n)
    if n <= 10:
        return _NATIVE_KO[n]
    tens, ones = divmod(n, 10)
    t = _NATIVE_KO.get(tens, str(tens)) if tens > 1 else ""
    return f"{t}열{_NATIVE_KO[ones]}" if ones else f"{t}열"


def preprocess_tts_text(text: str) -> str:
    """TTS 전처리: 숫자를 자연스러운 한국어 읽기로 변환."""

    # "1일 3회" → "하루 세 번"
    def _replace_daily(m: re.Match) -> str:
        n = int(m.group(1))
        return f"하루 {_native_num(n)} 번"

    text = re.sub(r"1일\s*(\d{1,2})\s*회", _replace_daily, text)

    # 숫자+단위 패턴 (1정, 2알, 3회 등) → 고유어
    def _replace_unit(m: re.Match) -> str:
        n = int(m.group(1))
        unit = m.group(2)
        mapped = _UNIT_MAP.get(unit, unit)
        return f"{_native_num(n)} {mapped}" if 1 <= n <= 99 else m.group(0)

    units_pattern = "|".join(re.escape(u) for u in _UNIT_MAP)
    text = re.sub(rf"(\d{{1,2}})\s*({units_pattern})", _replace_unit, text)

    # mg, ml 등 단위는 한국어 읽기로
    text = text.replace("mg", "밀리그램").replace("ml", "밀리리터")
    text = text.replace("g", "그램").replace("kg", "킬로그램")

    # 딱딱한 문어체 → 부드러운 대화체 변환
    _style = [
        ("복용하십시오", "드세요"),
        ("복용하시기 바랍니다", "드세요"),
        ("복용해야 합니다", "드셔야 해요"),
        ("복용합니다", "드세요"),
        ("섭취하십시오", "드세요"),
        ("섭취합니다", "드세요"),
        ("주의하십시오", "주의하세요"),
        ("주의해야 합니다", "주의하셔야 해요"),
        ("금지됩니다", "안 돼요"),
        ("금합니다", "피해주세요"),
        ("하십시오", "하세요"),
        ("하시기 바랍니다", "하세요"),
        ("않습니다", "않아요"),
        ("됩니다", "돼요"),
        ("합니다", "해요"),
        ("입니다", "이에요"),
        ("습니다", "세요"),
        ("십시오", "세요"),
        ("바랍니다", "주세요"),
    ]
    for formal, casual in _style:
        text = text.replace(formal, casual)

    return text


def _generate_audio_sync(text: str, lang: str) -> BytesIO:
    if lang == "ko":
        text = preprocess_tts_text(text)
    tts = gTTS(text=text, lang=lang, tld="co.kr")
    audio_fp = BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    return audio_fp


async def generate_tts(text: str, lang: str = "ko") -> BytesIO:
    """텍스트를 음성(MP3)으로 변환하여 BytesIO 객체로 반환"""
    loop = asyncio.get_running_loop()
    audio_fp = await loop.run_in_executor(None, _generate_audio_sync, text, lang)
    return audio_fp
