from pydantic import BaseModel, Field

class TTSRequest(BaseModel):
    text: str = Field(..., description="변환할 텍스트", min_length=1, max_length=5000)
    lang: str = Field("ko", description="언어 코드 (예: ko, en)")
