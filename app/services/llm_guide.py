"""
LLM Guide 서비스 — RAG 기반 의약품 안내.

핵심 책임:
1. FAISS 검색 결과의 신뢰도(score) 판별
2. 임계값 미달 시 답변 생성 차단 (안전 응답 반환)
3. System Prompt 조립 → LLM 호출 → 구조화 응답 생성

LLM 구성:
- 프론트 (채팅 응답): OpenAI GPT-4o-mini
- 백엔드 (RAG reasoning/agent): Zhipu GLM-5 via Kilo AI
"""

import logging
import re

from openai import AsyncOpenAI

from app.core.config import Config
from app.prompts.system_prompt import (
    DISCLAIMER,
    SAFE_FALLBACK_ANSWER,
    build_chat_prompt,
)

logger = logging.getLogger("llm_guide")

_cfg = Config()

# ── LLM 클라이언트 (OpenAI 호환) ─────────────
_glm_client = AsyncOpenAI(
    api_key=_cfg.GLM_API_KEY,
    base_url=_cfg.GLM_BASE_URL,
)

_openai_client = AsyncOpenAI(
    api_key=_cfg.OPENAI_API_KEY,
)


class LLMGuideService:
    """RAG + LLM 의약품 안내 서비스."""

    def __init__(
        self,
        confidence_threshold: float = _cfg.RAG_CONFIDENCE_THRESHOLD,
    ):
        self.confidence_threshold = confidence_threshold

    # ── 가드레일: 컨텍스트 검증 ───────────────
    def check_rag_confidence(self, scores: list[float]) -> bool:
        """검색 결과 신뢰도가 임계값을 충족하는지 판별합니다.

        Args:
            scores: FAISS 검색에서 반환된 cosine similarity 목록.
                    값이 높을수록 유사도가 높음 (0~1 범위).

        Returns:
            True면 답변 생성 가능, False면 안전 응답 반환.
        """
        if not scores:
            logger.warning("RAG 검색 결과 없음 — 안전 응답 반환")
            return False

        best_score = max(scores)
        passed = best_score >= self.confidence_threshold
        if not passed:
            logger.info(
                "RAG 임계값 미달: best_score=%.4f < threshold=%.4f",
                best_score,
                self.confidence_threshold,
            )
        return passed

    # ── 안전 응답 생성 ────────────────────────
    @staticmethod
    def build_safe_response() -> dict:
        """임계값 미달 시 반환할 안전 응답을 생성합니다."""
        return {
            "success": False,
            "error_code": "LOW_RAG_CONFIDENCE",
        }

    # ── 프롬프트 조립 ────────────────────────
    @staticmethod
    def build_prompt(context: str, question: str) -> str:
        """Context와 질문을 System Prompt에 주입합니다."""
        return build_chat_prompt(context=context, question=question)

    # ── 응답 후처리: 섹션 파싱 ────────────────
    @staticmethod
    def parse_sections(raw_answer: str) -> dict:
        """LLM 원문 답변에서 4개 섹션을 추출합니다.

        파싱 실패 시 전체 텍스트를 summary에 넣고 나머지는 기본값 처리.
        """
        default = "해당 정보가 제공되지 않았습니다."
        sections = {
            "summary": default,
            "dosage": default,
            "precautions": default,
            "tips": default,
        }

        section_map = {
            "summary": r"(?:\*{0,2}(?:summary|요약)\*{0,2})[:\s]*(.+?)(?=\n\s*\*{0,2}(?:dosage|복용|precautions|주의|tips|팁)|$)",
            "dosage": r"(?:\*{0,2}(?:dosage|복용(?:법|량)?)\*{0,2})[:\s]*(.+?)(?=\n\s*\*{0,2}(?:precautions|주의|tips|팁)|$)",
            "precautions": r"(?:\*{0,2}(?:precautions|주의(?:사항)?)\*{0,2})[:\s]*(.+?)(?=\n\s*\*{0,2}(?:tips|팁|보관|추가)|$)",
            "tips": r"(?:\*{0,2}(?:tips|팁|보관|추가(?:\s*안내)?)\*{0,2})[:\s]*(.+?)$",
        }

        for key, pattern in section_map.items():
            match = re.search(pattern, raw_answer, re.DOTALL | re.IGNORECASE)
            if match:
                text = match.group(1).strip()
                if text:
                    sections[key] = text

        # 어떤 섹션도 매칭 안 되면 전체 텍스트를 summary에 넣기
        all_default = all(v == default for v in sections.values())
        if all_default and raw_answer.strip():
            sections["summary"] = raw_answer.strip()

        return sections

    # ── 응답 후처리: TTS 세그먼트 분할 ───────
    MAX_TTS_CHARS = 200

    @classmethod
    def split_tts_segments(cls, text: str) -> list[str]:
        """답변 텍스트를 TTS 재생에 적합한 문장 단위로 분할합니다.

        1차: 줄바꿈 분리 → 2차: 문장부호 분리 → 3차: 길이 초과 시 쉼표 분리
        """
        # 1차: 줄바꿈으로 분리
        lines = text.split("\n")
        segments: list[str] = []

        for line in lines:
            line = line.strip()
            line = re.sub(r"^[-•*]\s*", "", line).strip()  # 불릿 제거
            if not line:
                continue

            # 2차: 문장부호(. ! ? 。)로 분리
            sentences = re.split(r"(?<=[.!?。])\s*", line)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                # 3차: 길이 초과 시 쉼표로 분리
                if len(sent) > cls.MAX_TTS_CHARS:
                    parts = sent.split(", ")
                    for p in parts:
                        p = p.strip()
                        if p:
                            segments.append(p)
                else:
                    segments.append(sent)

        return segments

    # ── 최종 응답 조립 ────────────────────────
    def build_success_response(
        self,
        raw_answer: str,
        citations: list[dict],
    ) -> dict:
        """LLM 원문 답변을 계약서 형식의 응답으로 변환합니다."""
        sections = self.parse_sections(raw_answer)
        full_text = raw_answer.strip()

        return {
            "success": True,
            "answer": full_text,
            "sections": sections,
            "tts_segments": self.split_tts_segments(full_text),
            "citations": citations,
            "disclaimer": DISCLAIMER,
        }

    # ── LLM 호출 ─────────────────────────────────
    async def call_glm(self, prompt: str) -> str:
        """GLM-5 (백엔드 reasoning) 호출."""
        resp = await _glm_client.chat.completions.create(
            model=_cfg.GLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=_cfg.GLM_MAX_TOKENS,
            temperature=_cfg.GLM_TEMPERATURE,
        )
        msg = resp.choices[0].message
        content = msg.content or ""
        if not content.strip():
            # GLM-5 reasoning 모델: content가 비어있으면 reasoning 필드 사용
            raw = msg.model_dump()
            reasoning = raw.get("reasoning") or ""
            if not reasoning:
                # reasoning_details 배열에서 텍스트 추출
                for detail in raw.get("reasoning_details") or []:
                    if isinstance(detail, dict) and detail.get("text"):
                        reasoning = detail["text"]
                        break
            if reasoning.strip():
                logger.info("GLM-5: content 비어있음, reasoning 필드 사용 (%d자)", len(reasoning))
                content = reasoning
        return content

    async def call_openai(self, prompt: str) -> str:
        """GPT-4o-mini (프론트 채팅 응답) 호출."""
        resp = await _openai_client.chat.completions.create(
            model=_cfg.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=_cfg.OPENAI_MAX_TOKENS,
            temperature=_cfg.OPENAI_TEMPERATURE,
        )
        return resp.choices[0].message.content or ""

    async def generate_answer(self, context: str, question: str) -> str:
        """RAG 컨텍스트 + 질문으로 LLM 답변 생성.

        GLM-5 우선 호출, 빈 응답 시 GPT-4o-mini fallback.
        """
        prompt = self.build_prompt(context=context, question=question)
        answer = await self.call_glm(prompt)
        if not answer.strip():
            logger.warning("GLM-5 빈 응답 — GPT-4o-mini fallback")
            answer = await self.call_openai(prompt)
        return answer

    # ── 컨텍스트 외 질문 감지 (추가 가드레일) ─
    @staticmethod
    def contains_out_of_scope_marker(answer: str) -> bool:
        """LLM 응답에 안전 응답 문구가 포함되어 있는지 확인합니다.

        LLM이 프롬프트 지시에 따라 스스로 안전 응답을 반환한 경우를 감지합니다.
        """
        return SAFE_FALLBACK_ANSWER in answer
