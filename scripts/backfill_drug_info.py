"""
빈 데이터 보충 스크립트 — knowledge_base.json의 빈 엔트리를 e약은요 API로 재시도.

기존 fetch_drug_info.py보다 공격적인 이름 매칭 전략 사용:
  1) 원본 이름 그대로
  2) 괄호/제조사/수량 제거
  3) 숫자+단위 꼬리 제거
  4) 핵심 약명만 (제형 접미사 포함)
  5) 핵심 약명 (제형 접미사 제거)
  6) 성분명 추출 시도

사용법:
    python scripts/backfill_drug_info.py                 # 전체 빈 엔트리 보충
    python scripts/backfill_drug_info.py --limit 100     # 100건만 테스트
    python scripts/backfill_drug_info.py --dry-run       # API 호출 없이 검색어만 확인
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ── 경로 설정 ────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "data" / "knowledge_base.json"
BACKUP_PATH = ROOT / "data" / "knowledge_base_backup.json"

# ── 식약처 e약은요 API ────────────────────────────
API_BASE = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

FIELD_MAP = {
    "efcyQesitm": "efficacy",
    "useMethodQesitm": "dosage",
    "atpnQesitm": "precautions",
    "atpnWarnQesitm": "warnings",
    "intrcQesitm": "interactions",
    "seQesitm": "side_effects",
    "depositMethodQesitm": "storage",
}

# ── 로깅 ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("backfill")


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_search_names(product_name: str) -> list[str]:
    """더 공격적인 검색 키워드 생성."""
    candidates: list[str] = []
    seen: set[str] = set()
    name = product_name.strip()

    def add(s: str) -> None:
        s = s.strip()
        if s and s not in seen and len(s) >= 2:
            candidates.append(s)
            seen.add(s)

    # 1) 괄호 내용 제거
    no_paren = re.sub(r"\s*\([^)]*\)", "", name).strip()

    # 2) 수량 꼬리 제거 (200T, 10C, 100정 등)
    no_qty = re.sub(r"\s+\d+[TCc정캡].*$", "", no_paren).strip()

    # 3) 숫자+단위 꼬리 제거 (400mg, 100밀리그람 등)
    no_dose = re.sub(r"\s*\d+\s*(mg|MG|밀리그.*|마이크로.*)\s*$", "", no_qty).strip()
    # 더 공격적: 숫자+단위가 이름 중간에 있을 수도 있음
    no_dose2 = re.sub(r"\d+\s*(mg|MG|밀리그.*)", "", no_paren).strip()
    no_dose2 = re.sub(r"\s+", "", no_dose2)  # 공백 제거 후 재시도용

    # 4) 제형 접미사 포함/제거
    form_suffixes = ["정", "캡슐", "캅셀", "산", "액", "시럽", "연질캡슐", "장용정", "서방정", "츄어블정", "트로키"]
    core = no_dose
    for suffix in form_suffixes:
        if core.endswith(suffix) and len(core) > len(suffix) + 1:
            core_no_form = core[: -len(suffix)]
            add(core)
            add(core_no_form)
            break
    else:
        add(core)

    # 5) 제조사명 제거 패턴들
    company_patterns = [
        r"^(한미|대웅|유한|삼진|영진|초당|경보|삼익|광동|명문|경동|유영|휴텍스|씨엠지|마더스|서울|글로|프라임|하원|휴비스트|보령|구주|태극|삼남|이텍스|삼일|대원|동아|종근당|일양|한독|JW|SK|CJ|GC|녹십자)",
        r"(제약|약품|바이오파마|바이오|코리아)\s*$",
    ]
    cleaned = no_qty
    for pat in company_patterns:
        cleaned = re.sub(pat, "", cleaned).strip()
    add(cleaned)

    # 6) 원본 변형들 추가
    add(no_paren)
    add(no_qty)
    add(no_dose)

    # 7) 맨 앞에 제조사가 붙은 경우: 제조사 제거
    # 예: "한미아스피린장용정100밀리그램" → "아스피린장용정"
    if len(no_qty) > 4:
        # 한글 2~4글자 제조사 + 약명
        match = re.match(r"^[가-힣]{2,4}(?=.{3,})", no_qty)
        if match:
            without_company = no_qty[match.end() :]
            add(without_company)
            # 추가로 제형/용량도 제거
            without_form = re.sub(r"(장용|서방|제피|츄어블)?정\d*.*$", "", without_company).strip()
            if without_form and without_form != without_company:
                add(without_form)

    return candidates


def fetch_from_api(api_key: str, search_name: str) -> dict | None:
    """e약은요 API 단건 검색."""
    params = {
        "serviceKey": api_key,
        "itemName": search_name,
        "type": "json",
        "numOfRows": "3",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params, safe='%+')}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        items = data.get("body", {}).get("items", [])
        if not items:
            return None

        item = items[0]
        result = {
            "api_item_name": item.get("itemName", ""),
            "company": item.get("entpName", ""),
        }
        for api_field, our_field in FIELD_MAP.items():
            result[our_field] = strip_html(item.get(api_field))
        return result
    except Exception:
        return None


def backfill_entry(api_key: str, entry: dict, sleep_sec: float) -> bool:
    """빈 엔트리에 대해 여러 검색어로 API 재시도. 성공 시 True."""
    search_names = build_search_names(entry["name"])

    for search_name in search_names:
        result = fetch_from_api(api_key, search_name)
        if result and result.get("efficacy"):
            # 성공 — 엔트리 업데이트
            for field in FIELD_MAP.values():
                if result.get(field):
                    entry[field] = result[field]
            entry["api_item_name"] = result.get("api_item_name", "")
            entry["company"] = result.get("company", "")
            return True
        time.sleep(sleep_sec)

    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="빈 데이터 보충 (e약은요 API 재시도)")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    parser.add_argument("--sleep", type=float, default=0.3, help="API 호출 간격(초)")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 검색어만 출력")
    parser.add_argument(
        "--category", choices=["일반의약품", "전문의약품", "all"], default="all", help="보충할 카테고리 (기본: all)"
    )
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("DATA_GO_KR_API_KEY_ENCODED", "")
    if not api_key and not args.dry_run:
        log.error("DATA_GO_KR_API_KEY_ENCODED가 .env에 없습니다")
        sys.exit(1)

    # 기존 KB 로드
    kb_data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    medications = kb_data["medications"]

    # 빈 엔트리 필터링
    empty_entries = [
        m
        for m in medications
        if not m.get("efficacy") and (args.category == "all" or m.get("category") == args.category)
    ]

    if args.limit:
        empty_entries = empty_entries[: args.limit]

    log.info("보충 대상: %d건 (전체 %d건 중)", len(empty_entries), len(medications))

    if args.dry_run:
        for entry in empty_entries[:20]:
            names = build_search_names(entry["name"])
            log.info("[%s] %s → 검색어: %s", entry["category"][:2], entry["name"], names)
        return

    # 백업 생성
    import shutil

    shutil.copy2(KB_PATH, BACKUP_PATH)
    log.info("백업 저장: %s", BACKUP_PATH)

    success_count = 0
    fail_count = 0

    for i, entry in enumerate(empty_entries):
        ok = backfill_entry(api_key, entry, args.sleep)
        if ok:
            success_count += 1
            log.info("OK [%d/%d] %s -> %s", i + 1, len(empty_entries), entry["name"], entry.get("api_item_name", ""))
        else:
            fail_count += 1

        if (i + 1) % 50 == 0:
            log.info("진행: %d/%d (성공: %d, 실패: %d)", i + 1, len(empty_entries), success_count, fail_count)
            # 중간 저장
            kb_data["total"] = len(medications)
            KB_PATH.write_text(
                json.dumps(kb_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # 최종 저장
    kb_data["total"] = len(medications)
    KB_PATH.write_text(
        json.dumps(kb_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log.info("완료! 보충 성공: %d건, 실패: %d건", success_count, fail_count)
    log.info(
        "기존 데이터: %d건 + 신규: %d건 = 총 %d건",
        len(medications) - len(empty_entries),
        success_count,
        len(medications) - len(empty_entries) + success_count,
    )


if __name__ == "__main__":
    main()
