"""
실시간 의약품 조회 서비스 — RAG에서 못 찾은 신약/미수록 약품 대응.

조회 순서:
  1) 식약처 e약은요 API (일반의약품 위주)
  2) DUR API + nedrug PDF (전문의약품 포함 전체)

결과를 RAG 컨텍스트와 동일한 포맷으로 반환 → LLM 프롬프트에 바로 주입 가능.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import urllib.parse
import urllib.request

from app.core.config import Config

logger = logging.getLogger("live_drug_lookup")
_cfg = Config()

# ── API 엔드포인트 ────────────────────────────────
_EASY_DRUG_API = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
_DUR_API = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getDurPrdlstInfoList03"
_NEDRUG_PDF = "https://nedrug.mfds.go.kr/dsie/pdf/drb"

# ── 필드 매핑 (e약은요) ───────────────────────────
_EASY_DRUG_FIELDS = {
    "efcyQesitm": "효능/효과",
    "useMethodQesitm": "용법/용량",
    "atpnQesitm": "주의사항",
    "atpnWarnQesitm": "경고",
    "intrcQesitm": "상호작용",
    "seQesitm": "부작용",
    "depositMethodQesitm": "보관법",
}


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_drug_name_from_query(query: str) -> str:
    """질문 문장에서 약품명을 추출합니다.

    예) "키트루다 알려줘" → "키트루다"
        "마이암부톨 주의사항" → "마이암부톨"
        "엔허투 부작용 뭐야" → "엔허투"
    """
    # 제거할 동사/조사/질문 패턴
    stop_patterns = [
        r"(알려줘|알려주세요|뭐야|뭔가요|무엇인가요|어때|어때요)\s*$",
        r"(주의사항|부작용|용법|용량|효능|효과|정보|설명|복용법|보관|성분)\s*$",
        r"\s+(이|가|은|는|의|을|를|에|에서|으로|으로는|란|이란|이란|에 대해|에 대해서)\s*$",
        r"\s+(어떻게|어떤|무슨|뭔|뭐)\s+(약|약인가요|약이에요|약이야)\s*$",
    ]
    name = query.strip()
    for pat in stop_patterns:
        name = re.sub(pat, "", name, flags=re.IGNORECASE).strip()

    # 여러 단어면 첫 단어(약품명) 추출
    # e.g. "마이암부톨 주의사항" → "마이암부톨"
    tokens = name.split()
    if len(tokens) > 1:
        # 마지막 단어가 일반 명사(주의사항/부작용 등)면 제거
        common_words = {
            "주의사항",
            "부작용",
            "용법",
            "용량",
            "효능",
            "효과",
            "정보",
            "설명",
            "복용법",
            "보관",
            "성분",
            "알려줘",
            "뭐야",
            "어때",
        }
        while len(tokens) > 1 and tokens[-1] in common_words:
            tokens.pop()
        name = " ".join(tokens)

    return name.strip()


def _build_search_names(drug_name: str) -> list[str]:
    """약품명에서 검색 키워드 후보를 생성."""
    candidates: list[str] = []
    seen: set[str] = set()

    # 먼저 질문에서 약품명 추출
    extracted = _extract_drug_name_from_query(drug_name)
    name = extracted if extracted else drug_name.strip()

    def add(s: str) -> None:
        s = s.strip()
        if s and s not in seen and len(s) >= 2:
            candidates.append(s)
            seen.add(s)

    # 괄호 제거
    no_paren = re.sub(r"\s*\([^)]*\)", "", name).strip()
    # 수량 제거
    no_qty = re.sub(r"\s+\d+[TCc정캡].*$", "", no_paren).strip()
    # 용량 제거 (소수점/분수/복합용량 포함: 2.5mg, 25-250mg, 50/500mg)
    no_dose = re.sub(r"\s*[\d./-]+\s*(mg|MG|밀리그.*|IU|mcg|MCG|μg|mL|ML)\s*$", "", no_qty).strip()
    # 숫자만 남은 경우 추가 제거 (e.g. "정 2." → "정")
    no_dose = re.sub(r"\s+[\d./-]+\s*$", "", no_dose).strip()

    add(no_paren)
    add(no_qty)
    add(no_dose)

    # 앞 제조사 제거 (no_qty, no_dose 모두 적용)
    for base in (no_qty, no_dose):
        if len(base) > 4:
            m = re.match(r"^[가-힣]{2,4}(?=.{3,})", base)
            if m:
                stripped = base[m.end() :]
                add(stripped)
                # 제조사 제거 후 용량도 제거
                stripped_no_dose = re.sub(
                    r"\s*[\d./-]+\s*(mg|MG|밀리그.*|IU|mcg|MCG|μg|mL|ML)\s*$", "", stripped
                ).strip()
                stripped_no_dose = re.sub(r"\s+[\d./-]+\s*$", "", stripped_no_dose).strip()
                add(stripped_no_dose)

    return candidates


def _fetch_url(url: str, timeout: int = 10) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _easy_drug_lookup(search_name: str) -> dict | None:
    """e약은요 API 단건 조회."""
    api_key = _cfg.DATA_GO_KR_API_KEY_ENCODED
    if not api_key:
        return None
    params = {
        "serviceKey": api_key,
        "itemName": search_name,
        "type": "json",
        "numOfRows": "3",
    }
    url = f"{_EASY_DRUG_API}?{urllib.parse.urlencode(params, safe='%+')}"
    raw = _fetch_url(url)
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        items = data.get("body", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        result: dict[str, str] = {
            "name": item.get("itemName", ""),
            "company": item.get("entpName", ""),
            "category": "일반의약품",
        }
        for api_field, label in _EASY_DRUG_FIELDS.items():
            val = _strip_html(item.get(api_field))
            if val:
                result[label] = val
        return result if result.get("효능/효과") else None
    except Exception:
        return None


def _dur_lookup(search_name: str) -> dict | None:
    """DUR API로 ITEM_SEQ + 기본정보 조회."""
    api_key = _cfg.DUR_PRDLST_INFO_API_KEY_ENCODED
    if not api_key:
        return None
    params = {
        "serviceKey": api_key,
        "itemName": search_name,
        "type": "json",
        "numOfRows": "3",
    }
    url = f"{_DUR_API}?{urllib.parse.urlencode(params, safe='%+')}"
    raw = _fetch_url(url)
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        items = data.get("body", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        return {
            "item_seq": str(item.get("ITEM_SEQ", "")),
            "name": item.get("ITEM_NAME", ""),
            "company": item.get("ENTP_NAME", ""),
            "storage": item.get("STORAGE_METHOD", ""),
        }
    except Exception:
        return None


def _extract_pdf_text(item_seq: str, doc_type: str) -> str:
    """nedrug PDF에서 텍스트 추출."""
    url = f"{_NEDRUG_PDF}/{item_seq}/{doc_type}"
    raw = _fetch_url(url, timeout=15)
    if not raw or len(raw) < 100:
        return ""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception:
        return ""


def _prmssn_lookup(search_name: str) -> dict | None:
    """허가정보 API로 ITEM_SEQ 조회 (DUR에 없는 신약 fallback)."""
    api_key = _cfg.DRUG_PRDT_PRMSN_INFO_API_KEY_ENCODED
    if not api_key:
        return None
    params = {
        "serviceKey": api_key,
        "item_name": search_name,
        "type": "json",
        "numOfRows": "3",
    }
    url = f"https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07?{urllib.parse.urlencode(params, safe='%+')}"
    raw = _fetch_url(url)
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        items = data.get("body", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        return {
            "item_seq": str(item.get("ITEM_SEQ", "")),
            "name": item.get("ITEM_NAME", ""),
            "company": item.get("ENTP_NAME", ""),
            "storage": "",
        }
    except Exception:
        return None


def _dur_pdf_lookup(search_name: str) -> dict | None:
    """DUR API + nedrug PDF로 전문의약품 정보 조회. DUR 실패 시 허가정보 API로 fallback."""
    dur = _dur_lookup(search_name) or _prmssn_lookup(search_name)
    if not dur or not dur.get("item_seq"):
        return None
    item_seq = dur["item_seq"]

    ee = _extract_pdf_text(item_seq, "EE")
    if not ee:
        return None

    ud = _extract_pdf_text(item_seq, "UD")
    nb = _extract_pdf_text(item_seq, "NB")

    return {
        "name": dur["name"],
        "company": dur["company"],
        "category": "전문의약품",
        "효능/효과": ee,
        "용법/용량": ud,
        "주의사항": nb,
        "보관법": dur.get("storage", ""),
    }


def _build_context_from_info(info: dict) -> str:
    """조회 결과를 RAG 컨텍스트 포맷으로 변환."""
    name = info.get("name", "")
    company = info.get("company", "")
    category = info.get("category", "")

    lines = [f"[약품명] {name} ({category}) — {company}"]
    field_map = {
        "효능/효과": "효능/효과",
        "용법/용량": "용법/용량",
        "주의사항": "주의사항",
        "경고": "경고",
        "상호작용": "상호작용",
        "부작용": "부작용",
        "보관법": "보관법",
    }
    for key, label in field_map.items():
        val = info.get(key, "").strip()
        if val:
            lines.append(f"[{label}] {val[:1000]}")  # 너무 길면 잘라냄

    return "\n".join(lines)


def lookup_drug(drug_name: str) -> tuple[str, str] | None:
    """
    실시간 약품 조회.

    Returns:
        (context_text, drug_name) 또는 None (찾지 못한 경우).
    """
    search_names = _build_search_names(drug_name)

    for name in search_names:
        # 1) e약은요 (빠름, 일반의약품 위주)
        info = _easy_drug_lookup(name)
        if info:
            logger.info("실시간 조회 성공 (e약은요): %s -> %s", drug_name, info.get("name"))
            return _build_context_from_info(info), info.get("name", drug_name)

    for name in search_names:
        # 2) DUR + PDF (느림, 전문의약품 포함)
        info = _dur_pdf_lookup(name)
        if info:
            logger.info("실시간 조회 성공 (DUR+PDF): %s -> %s", drug_name, info.get("name"))
            return _build_context_from_info(info), info.get("name", drug_name)

    logger.info("실시간 조회 실패: %s", drug_name)
    return None


async def lookup_drug_async(drug_name: str) -> tuple[str, str] | None:
    """비동기 래퍼 — FastAPI async 라우터에서 호출 가능."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lookup_drug, drug_name)
