"""
knowledge_base.json → FAISS 인덱스 생성 스크립트.

Chunk 규칙: 약품 1건 = 문서 1개 (전체 텍스트 필드 결합)
임베딩 모델: paraphrase-multilingual-MiniLM-L12-v2 (384차원)

사용법:
    python scripts/build_faiss_index.py
    python scripts/build_faiss_index.py --model jhgan/ko-sbert-nli
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import faiss
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KB_PATH = DATA_DIR / "knowledge_base.json"
INDEX_PATH = DATA_DIR / "faiss_index.bin"
META_PATH = DATA_DIR / "faiss_meta.json"

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("build_faiss")


# ── Chunk 생성 ───────────────────────────────────
def medication_to_chunk(med: dict) -> str:
    """약품 1건의 텍스트 필드를 하나의 검색 문서로 결합합니다.

    Chunk 규칙:
    - 약품명 + 카테고리를 헤더로
    - 효능, 용법, 주의사항, 경고, 상호작용, 부작용, 보관법을 섹션으로
    - 빈 필드는 제외하여 노이즈 최소화
    """
    parts: list[str] = []

    # 헤더
    name = med.get("name", "")
    category = med.get("category", "")
    company = med.get("company", "")
    header = f"[약품명] {name}"
    if category:
        header += f" ({category})"
    if company:
        header += f" — {company}"
    parts.append(header)

    # 본문 섹션
    field_labels = [
        ("efficacy", "효능/효과"),
        ("dosage", "용법/용량"),
        ("precautions", "주의사항"),
        ("warnings", "경고"),
        ("interactions", "상호작용"),
        ("side_effects", "부작용"),
        ("storage", "보관법"),
    ]
    for field, label in field_labels:
        value = med.get(field, "").strip()
        if value:
            parts.append(f"[{label}] {value}")

    return "\n".join(parts)


def build_chunks(medications: list[dict]) -> tuple[list[str], list[dict]]:
    """전체 약품 목록에서 비어있지 않은 청크와 메타데이터를 생성합니다."""
    chunks: list[str] = []
    meta: list[dict] = []

    for med in medications:
        chunk = medication_to_chunk(med)
        # 헤더만 있고 본문이 없는 경우 제외
        if chunk.count("\n") == 0:
            continue

        chunks.append(chunk)
        meta.append({
            "medication_id": med.get("medication_id", ""),
            "name": med.get("name", ""),
            "category": med.get("category", ""),
            "c_code": med.get("c_code", ""),
            "source": med.get("source", ""),
        })

    return chunks, meta


# ── 메인 ──────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="FAISS 인덱스 빌드")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="SentenceTransformer 모델명")
    parser.add_argument("--batch-size", type=int, default=64, help="임베딩 배치 크기")
    args = parser.parse_args()

    # 1) knowledge_base.json 로드
    if not KB_PATH.exists():
        log.error("knowledge_base.json이 없습니다: %s", KB_PATH)
        sys.exit(1)

    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    medications = kb.get("medications", [])
    log.info("약품 %d건 로드", len(medications))

    # 2) 청크 생성
    chunks, meta = build_chunks(medications)
    log.info("유효 청크 %d건 생성 (빈 문서 %d건 제외)", len(chunks), len(medications) - len(chunks))

    if not chunks:
        log.error("유효한 청크가 없습니다")
        sys.exit(1)

    # 3) 임베딩 생성
    log.info("임베딩 모델 로드: %s", args.model)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model)

    log.info("임베딩 생성 시작 (batch_size=%d)...", args.batch_size)
    t0 = time.time()
    embeddings = model.encode(
        chunks,
        batch_size=args.batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    elapsed = time.time() - t0
    log.info("임베딩 완료: %.1f초 (차원: %d)", elapsed, embeddings.shape[1])

    # 4) FAISS 인덱스 생성
    dim = embeddings.shape[1]
    embeddings_np = np.array(embeddings, dtype=np.float32)

    index = faiss.IndexFlatIP(dim)  # 정규화된 벡터이므로 Inner Product = Cosine Similarity
    index.add(embeddings_np)
    log.info("FAISS 인덱스 생성: %d 벡터, 차원 %d", index.ntotal, dim)

    # 5) 저장 (한글 경로 대응: serialize → Python IO)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    index_bytes = faiss.serialize_index(index)
    INDEX_PATH.write_bytes(index_bytes)
    log.info("인덱스 저장: %s (%d bytes)", INDEX_PATH, len(index_bytes))

    META_PATH.write_text(
        json.dumps(
            {
                "model": args.model,
                "dimension": dim,
                "total": len(meta),
                "entries": meta,
                "chunks": chunks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("메타데이터 저장: %s", META_PATH)

    log.info("완료!")


if __name__ == "__main__":
    main()
