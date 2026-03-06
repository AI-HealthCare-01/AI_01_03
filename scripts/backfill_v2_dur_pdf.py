"""
빈 데이터 보충 v2 — DUR API + nedrug PDF 텍스트 추출.

e약은요 API에 없는 약품(주로 전문의약품)을 DUR API로 ITEM_SEQ를 확보하고,
nedrug.mfds.go.kr의 PDF에서 효능효과/용법용량/주의사항 텍스트를 추출합니다.

사용법:
    python scripts/backfill_v2_dur_pdf.py                # 전체 빈 엔트리 보충
    python scripts/backfill_v2_dur_pdf.py --limit 50     # 50건만 테스트
    python scripts/backfill_v2_dur_pdf.py --dry-run      # API 호출 없이 대상만 확인
"""

from __future__ import annotations

import argparse
import io
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
BACKUP_PATH = ROOT / "data" / "knowledge_base_backup_v2.json"

# ── API 설정 ─────────────────────────────────────
DUR_API_BASE = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getDurPrdlstInfoList03"
PRMSSN_API_BASE = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"
NEDRUG_PDF_BASE = "https://nedrug.mfds.go.kr/dsie/pdf/drb"

# ── 로깅 ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("backfill_v2")


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
    """제품명에서 검색 키워드 생성."""
    candidates: list[str] = []
    seen: set[str] = set()
    name = product_name.strip()

    def add(s: str) -> None:
        s = s.strip()
        if s and s not in seen and len(s) >= 2:
            candidates.append(s)
            seen.add(s)

    no_paren = re.sub(r"\s*\([^)]*\)", "", name).strip()
    no_qty = re.sub(r"\s+\d+[TCc정캡].*$", "", no_paren).strip()
    # 소수점/분수/복합용량 포함 (2.5mg, 25-250mg, 50/500mg)
    no_dose = re.sub(r"\s*[\d./-]+\s*(mg|MG|밀리그.*|IU|mcg|MCG|μg|mL|ML)\s*$", "", no_qty).strip()
    # 숫자만 남은 경우 추가 제거 (e.g. "정 2." → "정")
    no_dose = re.sub(r"\s+[\d./-]+\s*$", "", no_dose).strip()

    add(no_paren)
    add(no_qty)
    add(no_dose)

    # 제조사 prefix 제거 (no_qty, no_dose 모두 적용)
    for base in (no_qty, no_dose):
        if len(base) > 4:
            match = re.match(r"^[가-힣]{2,4}(?=.{3,})", base)
            if match:
                stripped = base[match.end() :]
                add(stripped)
                # 제조사 제거 후 용량도 제거
                stripped_no_dose = re.sub(r"\s*[\d./-]+\s*(mg|MG|밀리그.*|IU|mcg|MCG|μg|mL|ML)\s*$", "", stripped).strip()
                stripped_no_dose = re.sub(r"\s+[\d./-]+\s*$", "", stripped_no_dose).strip()
                add(stripped_no_dose)

    return candidates


def fetch_dur_info(api_key: str, search_name: str) -> dict | None:
    """DUR API로 약품 기본 정보 조회."""
    params = {
        "serviceKey": api_key,
        "itemName": search_name,
        "type": "json",
        "numOfRows": "3",
    }
    url = f"{DUR_API_BASE}?{urllib.parse.urlencode(params, safe='%+')}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("body", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        return {
            "item_seq": item.get("ITEM_SEQ", ""),
            "item_name": item.get("ITEM_NAME", ""),
            "company": item.get("ENTP_NAME", ""),
            "material": item.get("MATERIAL_NAME", ""),
            "storage": item.get("STORAGE_METHOD", ""),
        }
    except Exception:
        return None


def fetch_prmssn_info(api_key: str, search_name: str) -> dict | None:
    """허가정보 API로 ITEM_SEQ 조회 (DUR에 없는 경우 fallback)."""
    params = {
        "serviceKey": api_key,
        "item_name": search_name,
        "type": "json",
        "numOfRows": "3",
    }
    url = f"{PRMSSN_API_BASE}?{urllib.parse.urlencode(params, safe='%+')}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("body", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        return {
            "item_seq": item.get("ITEM_SEQ", ""),
            "item_name": item.get("ITEM_NAME", ""),
            "company": item.get("ENTP_NAME", ""),
            "material": item.get("ITEM_INGR_NAME", ""),
            "storage": "",
        }
    except Exception:
        return None


def extract_pdf_text(item_seq: str, doc_type: str) -> str:
    """nedrug PDF에서 텍스트 추출. doc_type: EE, UD, NB"""
    url = f"{NEDRUG_PDF_BASE}/{item_seq}/{doc_type}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            pdf_data = resp.read()

        if len(pdf_data) < 100:
            return ""

        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(pdf_data))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception:
        return ""


def parse_material_name(material_str: str) -> str:
    """DUR MATERIAL_NAME 필드에서 주성분명 추출."""
    if not material_str:
        return ""
    # Format: "성분명,,용량,단위,약전," 반복
    parts = material_str.split("/")
    ingredients = []
    for part in parts:
        fields = part.split(",")
        if fields and fields[0].strip():
            ingredients.append(fields[0].strip())
    return ", ".join(ingredients)


def backfill_entry(dur_key: str, prmssn_key: str, entry: dict, sleep_sec: float) -> bool:
    """빈 엔트리에 대해 DUR + PDF로 데이터 보충."""
    search_names = build_search_names(entry["name"])

    # Step 1: DUR API로 ITEM_SEQ 확보
    dur_info = None
    for name in search_names:
        dur_info = fetch_dur_info(dur_key, name)
        if dur_info and dur_info.get("item_seq"):
            break
        time.sleep(sleep_sec)

    # Fallback: 허가정보 API
    if not dur_info or not dur_info.get("item_seq"):
        for name in search_names:
            dur_info = fetch_prmssn_info(prmssn_key, name)
            if dur_info and dur_info.get("item_seq"):
                break
            time.sleep(sleep_sec)

    if not dur_info or not dur_info.get("item_seq"):
        return False

    item_seq = str(dur_info["item_seq"])

    # Step 2: PDF에서 텍스트 추출
    ee_text = extract_pdf_text(item_seq, "EE")
    ud_text = extract_pdf_text(item_seq, "UD")
    nb_text = extract_pdf_text(item_seq, "NB")

    # 최소 효능효과 텍스트가 있어야 성공으로 간주
    if not ee_text:
        return False

    # Step 3: 엔트리 업데이트
    entry["efficacy"] = ee_text
    entry["dosage"] = ud_text
    entry["precautions"] = nb_text
    entry["storage"] = dur_info.get("storage", "") or entry.get("storage", "")
    entry["api_item_name"] = dur_info.get("item_name", "")
    entry["company"] = dur_info.get("company", "")

    # 성분명 파싱해서 warnings에 저장 (기존 warnings 필드가 비어있으면)
    if not entry.get("warnings") and dur_info.get("material"):
        material = parse_material_name(dur_info["material"])
        if material:
            entry["warnings"] = f"주성분: {material}"

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="빈 데이터 보충 v2 (DUR + PDF)")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    parser.add_argument("--sleep", type=float, default=0.3, help="API 호출 간격(초)")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 대상만 확인")
    args = parser.parse_args()

    env = load_env()
    dur_key = env.get("DUR_PRDLST_INFO_API_KEY_ENCODED", "")
    prmssn_key = env.get("DRUG_PRDT_PRMSN_INFO_API_KEY_ENCODED", "")

    if not dur_key and not args.dry_run:
        log.error("DUR_PRDLST_INFO_API_KEY_ENCODED가 .env에 없습니다")
        sys.exit(1)

    # 기존 KB 로드
    kb_data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    medications = kb_data["medications"]

    # 빈 엔트리 필터링
    empty_entries = [m for m in medications if not m.get("efficacy")]

    if args.limit:
        empty_entries = empty_entries[: args.limit]

    log.info("보충 대상: %d건 (전체 %d건 중)", len(empty_entries), len(medications))

    if args.dry_run:
        for entry in empty_entries[:20]:
            names = build_search_names(entry["name"])
            log.info("[%s] %s -> %s", entry["category"][:2], entry["name"], names)
        return

    # 백업 생성
    import shutil

    shutil.copy2(KB_PATH, BACKUP_PATH)
    log.info("백업 저장: %s", BACKUP_PATH)

    success_count = 0
    fail_count = 0

    for i, entry in enumerate(empty_entries):
        ok = backfill_entry(dur_key, prmssn_key, entry, args.sleep)
        if ok:
            success_count += 1
            log.info(
                "OK [%d/%d] %s -> %s",
                i + 1,
                len(empty_entries),
                entry["name"],
                entry.get("api_item_name", ""),
            )
        else:
            fail_count += 1

        if (i + 1) % 50 == 0:
            log.info(
                "진행: %d/%d (성공: %d, 실패: %d)",
                i + 1,
                len(empty_entries),
                success_count,
                fail_count,
            )
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

    filled_total = sum(1 for m in medications if m.get("efficacy"))
    log.info("완료! 보충 성공: %d건, 실패: %d건", success_count, fail_count)
    log.info("전체 데이터 현황: %d/%d건 데이터 보유", filled_total, len(medications))


if __name__ == "__main__":
    main()
