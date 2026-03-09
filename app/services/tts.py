import asyncio
from io import BytesIO

from gtts import gTTS


def _generate_audio_sync(text: str, lang: str) -> BytesIO:
    tts = gTTS(text=text, lang=lang)
    audio_fp = BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    return audio_fp


async def generate_tts(text: str, lang: str = "ko") -> BytesIO:
    """텍스트를 음성(MP3)으로 변환하여 BytesIO 객체로 반환"""
    loop = asyncio.get_running_loop()
    audio_fp = await loop.run_in_executor(None, _generate_audio_sync, text, lang)
    return audio_fp
