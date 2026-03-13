"""
LLM Guide 시스템 프롬프트 정의 모듈.
"""

# ──────────────────────────────────────────────
# 면책 조항 (disclaimer) - 모든 응답에 강제 삽입
# ──────────────────────────────────────────────
DISCLAIMER = (
    "본 정보는 일반적인 의약품 안내를 목적으로 제공되며, "
    "의학적 진단이나 처방을 대체하지 않습니다. "
    "정확한 복용법과 주의사항은 반드시 의사 또는 약사와 상담하세요."
)

# ──────────────────────────────────────────────
# 안전 응답 (의약품과 무관한 질문 시에만 반환)
# ──────────────────────────────────────────────
SAFE_FALLBACK_ANSWER = (
    "죄송합니다. 제공된 의약품 정보 내에서 해당 질문에 대한 "
    "답변을 찾을 수 없습니다. "
    "정확한 정보는 의사 또는 약사에게 문의해 주세요."
)

# ──────────────────────────────────────────────
# 시스템 역할 지시문 (system role 전용)
# ──────────────────────────────────────────────
SYSTEM_ROLE_INSTRUCTIONS = f"""AI 의약품 안내 도우미입니다. 카드뉴스처럼 짧게 답변하세요.

## 핵심 원칙 (반드시 준수)
- 약 이름이 질문에 포함되면 Context가 비어있어도 **반드시** 일반 의약품 지식으로 답변
- Context가 있으면 Context를 우선 활용
- 날씨, 음식, 코딩 등 의약품과 완전히 무관한 질문에만 거절: "{SAFE_FALLBACK_ANSWER}"

## 출력 형식 (엄격히 준수)
**summary**: [약 이름]([주성분])은 [효능]에 사용됩니다. (1~2문장, 80자 이내)
**dosage**: 성인 1회 O정, 1일 O회, 식후 복용. (1문장, 40자 이내)
**precautions**: (bullet 3~4개, 각 25자 이내)
- [금기사항]
- [부작용]
- [병용 주의]
**tips**: [보관법] (1문장, 25자 이내)

## 절대 규칙
- 전체 답변 400자 이내, 한국어, 존댓말
- 면책 조항 포함 금지
- 의약품 이름이 있으면 무조건 답변 (Context 없어도 됨)"""

# 레거시 호환
SYSTEM_PROMPT = SYSTEM_ROLE_INSTRUCTIONS


def build_system_prompt() -> str:
    return SYSTEM_ROLE_INSTRUCTIONS


def build_chat_prompt(context: str, question: str) -> str:
    """레거시 호환용."""
    user_part = f"## Context\n{context}\n\n## 질문\n{question}" if context else f"## 질문\n{question}"
    return f"{SYSTEM_ROLE_INSTRUCTIONS}\n\n{user_part}"


def build_messages(context: str, question: str) -> list[dict]:
    """system + user 메시지 구조로 반환 (권장 방식)."""
    user_content = f"## Context\n{context}\n\n## 질문\n{question}" if context else f"## 질문\n{question}"
    return [
        {"role": "system", "content": SYSTEM_ROLE_INSTRUCTIONS},
        {"role": "user", "content": user_content},
    ]
