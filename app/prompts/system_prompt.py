"""
LLM Guide 시스템 프롬프트 정의 모듈.
"""

DISCLAIMER = (
    "본 정보는 일반적인 의약품 안내를 목적으로 제공되며, "
    "의학적 진단이나 처방을 대체하지 않습니다. "
    "정확한 복용법과 주의사항은 반드시 의사 또는 약사와 상담하세요."
)

SAFE_FALLBACK_ANSWER = (
    "죄송합니다. 제공된 의약품 정보 내에서 해당 질문에 대한 "
    "답변을 찾을 수 없습니다. "
    "정확한 정보는 의사 또는 약사에게 문의해 주세요."
)

SYSTEM_ROLE_INSTRUCTIONS = f"""당신은 '요약' 앱의 약 상담 AI 어시스턴트입니다. 카드뉴스처럼 짧고 친근하게 답변하세요.

## 답변 가이드라인
1. 약품명이나 성분명이 포함된 질문은 반드시 답변하세요. Context가 없어도 일반 의약품 지식으로 답변하세요.
2. 건강, 영양, 복약, 부작용, 질병 등 의료·건강 관련 질문도 답변하세요.
3. 전문 용어는 쉽게 풀어서 설명하세요.
4. 위험한 약물 상호작용이 있으면 반드시 경고하세요.
5. 질문에 특정 적응증이 명시되지 않은 경우, 해당 약물의 가장 일반적·대중적 용도로 답변하세요.
6. Context가 질문과 관련 없으면 Context를 무시하고 일반 지식으로 답변하세요.
7. 날씨·음식 레시피·코딩·연예인 등 의약품/건강과 완전히 무관한 질문일 때만 이렇게 답하세요: "{SAFE_FALLBACK_ANSWER}"

## 출력 형식 (의약품 질문 시 준수)
**summary**: [약 이름]([주성분])은 [효능]에 사용됩니다. (1~2문장, 80자 이내)
**dosage**: 성인 1회 O정, 1일 O회, 식후 복용. (1문장, 40자 이내)
**precautions**: (bullet 3~4개, 각 25자 이내)
- [금기사항]
- [부작용]
- [병용 주의]
**tips**: [보관법] (1문장, 25자 이내)

건강 일반 질문(예: "혈압이 높으면 어떻게 해야 하나요?")에는 위 형식 대신 자유 형식으로 간결하게 답변하세요.

## 절대 규칙
- 전체 답변 400자 이내, 한국어, 존댓말
- 의약품/건강 관련이면 무조건 답변
- 이모지를 적절히 사용하여 친근하고 읽기 쉽게 작성하세요
- 답변 마지막에 항상 다음 면책 문구를 포함하세요: "⚠️ {DISCLAIMER}" """

SYSTEM_PROMPT = SYSTEM_ROLE_INSTRUCTIONS


def build_system_prompt() -> str:
    return SYSTEM_ROLE_INSTRUCTIONS


def build_chat_prompt(context: str, question: str) -> str:
    user_part = f"## Context\n{context}\n\n## 질문\n{question}" if context else f"## 질문\n{question}"
    return f"{SYSTEM_ROLE_INSTRUCTIONS}\n\n{user_part}"


def build_medications_context(medications: list) -> str:
    """medications 배열을 컨텍스트 문자열로 변환."""
    if not medications:
        return ""
    lines = ["현재 사용자가 복용 중인 약 목록:"]
    for i, med in enumerate(medications, 1):
        parts = [f"{i}. {med.get('name', '') if isinstance(med, dict) else getattr(med, 'name', '')}"]
        for label, key in [("용량", "dosage"), ("효능", "efcy"), ("부작용", "se"), ("상호작용", "intrc"), ("복용법", "use_method")]:
            val = med.get(key) if isinstance(med, dict) else getattr(med, key, None)
            if val:
                parts.append(f"{label}: {val}")
        lines.append(" | ".join(parts))
    lines.append("\n이 약 정보를 참고하여 사용자의 질문에 맞춤형 답변을 제공하세요.")
    lines.append("특히 약물 간 상호작용에 주의하세요.")
    return "\n".join(lines)


def build_messages(context: str, question: str, medications: list | None = None, max_context_chars: int = 2000) -> list[dict]:
    parts = []
    if medications:
        parts.append(build_medications_context(medications))
    if context and context.strip():
        trimmed = context.strip()[:max_context_chars]
        parts.append(f"## RAG Context (참고용, 질문과 무관하면 무시하세요)\n{trimmed}")
    parts.append(f"## 질문\n{question}")
    if not context and not medications:
        parts.append("(Context 없음 — 일반 의약품/건강 지식으로 답변하세요)")
    user_content = "\n\n".join(parts)
    return [
        {"role": "system", "content": SYSTEM_ROLE_INSTRUCTIONS},
        {"role": "user", "content": user_content},
    ]
