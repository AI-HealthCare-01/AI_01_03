from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dtos.tts import TTSRequest
from app.services.tts import generate_tts

tts_router = APIRouter(prefix="/tts", tags=["TTS"])


@tts_router.post("/generate", summary="텍스트를 음성으로 변환")
async def generate_tts_endpoint(request: TTSRequest):
    """
    제공된 텍스트를 기반으로 음성 파일(mp3)을 생성하여 스트리밍합니다.
    클라이언트에서 오디오 자동 재생 및 컨트롤(음량, 속도)을 위해 사용할 수 있습니다.
    """
    audio_fp = await generate_tts(text=request.text, lang=request.lang)
    return StreamingResponse(audio_fp, media_type="audio/mpeg")
