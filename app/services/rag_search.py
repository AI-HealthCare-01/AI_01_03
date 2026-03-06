"""
FAISS 기반 RAG 검색 서비스.

인덱스 로드 → 쿼리 임베딩 → Top-K 검색 → 컨텍스트 + 스코어 반환.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("rag_search")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
INDEX_PATH = DATA_DIR / "faiss_index.bin"
META_PATH = DATA_DIR / "faiss_meta.json"


@dataclass
class SearchResult:
    """FAISS 검색 결과 1건."""

    score: float  # cosine similarity (높을수록 유사)
    chunk: str  # 원본 텍스트 청크
    medication_id: str
    name: str
    category: str
    source: str


class RAGSearchService:
    """FAISS 인덱스를 이용한 의약품 검색 서비스."""

    _instance: RAGSearchService | None = None

    def __init__(self) -> None:
        self._index: faiss.Index | None = None
        self._chunks: list[str] = []
        self._meta: list[dict] = []
        self._model: SentenceTransformer | None = None
        self._model_name: str = ""

    @classmethod
    def get_instance(cls) -> RAGSearchService:
        """싱글톤 인스턴스를 반환합니다."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load()
        return cls._instance

    def load(self) -> None:
        """FAISS 인덱스 + 메타데이터 + 임베딩 모델을 로드합니다."""
        meta_gz = META_PATH.with_suffix(".json.gz")

        # .gz 있으면 자동 압축 해제
        if not META_PATH.exists() and meta_gz.exists():
            import gzip
            import shutil

            logger.info("faiss_meta.json.gz → 압축 해제 중...")
            with gzip.open(meta_gz, "rb") as f_in, META_PATH.open("wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            logger.info("압축 해제 완료: %s", META_PATH)

        if not INDEX_PATH.exists() or not META_PATH.exists():
            logger.warning("FAISS 인덱스 없음 — Mock 모드로 동작합니다: %s", INDEX_PATH)
            return

        # 인덱스 로드 (한글 경로 대응: Python IO → deserialize)
        index_bytes = INDEX_PATH.read_bytes()
        self._index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype=np.uint8))
        logger.info("FAISS 인덱스 로드: %d 벡터", self._index.ntotal)

        # 메타데이터 로드
        meta_data = json.loads(META_PATH.read_text(encoding="utf-8"))
        self._meta = meta_data.get("entries", [])
        self._chunks = meta_data.get("chunks", [])
        self._model_name = meta_data.get("model", "paraphrase-multilingual-MiniLM-L12-v2")

        # 임베딩 모델 로드
        logger.info("임베딩 모델 로드: %s", self._model_name)
        self._model = SentenceTransformer(self._model_name)
        logger.info("RAG 검색 서비스 준비 완료")

    @property
    def is_ready(self) -> bool:
        return self._index is not None and self._model is not None

    @staticmethod
    def _extract_core_name(name: str) -> str:
        """약품명에서 핵심 이름만 추출합니다. '타이레놀정500mg(성인용)' → '타이레놀'"""
        import re

        # 괄호 이전 부분만
        name = name.split("(")[0].strip()
        # 숫자+단위 제거 (10T, 500mg, 150mg, 30T 등)
        name = re.sub(r"\s*\d+\s*[TtCcMmGg]+\s*$", "", name).strip()
        name = re.sub(r"\s*\d+mg\s*$", "", name, flags=re.IGNORECASE).strip()
        # 남은 숫자 제거
        name = re.sub(r"\s*\d+\s*$", "", name).strip()
        # 제형명 접미사 제거 (정, 캡슐, 시럽, 연질캡슐, 서방정 등)
        name = re.sub(
            r"(연질캡슐|서방정|이알서방정|캡슐|시럽|정제|산제|과립|현탁액|정)\s*$",
            "",
            name,
        ).strip()
        return name.lower()

    def _keyword_match_indices(self, query: str) -> list[int]:
        """쿼리에서 약품명 키워드와 일치하는 인덱스를 반환합니다.

        양방향 매칭: 약품 코어명이 쿼리에 포함되거나, 쿼리 단어가 약품 코어명에 포함.
        """
        matched: list[int] = []
        q_lower = query.lower()
        q_tokens = [t for t in q_lower.split() if len(t) >= 2]
        for i, m in enumerate(self._meta):
            core_name = self._extract_core_name(m.get("name", ""))
            if len(core_name) < 2:
                continue
            # 약품명 → 쿼리 포함 또는 쿼리 토큰 → 약품명 포함
            if core_name in q_lower or any(t in core_name for t in q_tokens):
                matched.append(i)
        return matched

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """하이브리드 검색: 약품명 키워드 매칭 + FAISS 벡터 검색.

        Returns:
            유사도 높은 순으로 정렬된 SearchResult 리스트.
            인덱스 미로드 시 빈 리스트 반환.
        """
        if not self.is_ready:
            logger.warning("FAISS 인덱스 미로드 — 빈 결과 반환")
            return []

        # 쿼리 임베딩
        query_vec = self._model.encode(
            [query],
            normalize_embeddings=True,
        )
        query_np = np.array(query_vec, dtype=np.float32)

        # FAISS 벡터 검색 (넉넉하게 가져옴)
        fetch_k = max(top_k * 3, 10)
        scores, indices = self._index.search(query_np, fetch_k)

        # 키워드 매칭 부스팅
        keyword_indices = set(self._keyword_match_indices(query))
        name_boost = 0.5  # 약품명 일치 시 score 부스트

        candidates: list[tuple[float, int]] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0 or idx >= len(self._chunks):
                continue
            boosted = float(score) + name_boost if idx in keyword_indices else float(score)
            candidates.append((boosted, int(idx)))

        # 키워드 매치인데 FAISS에 안 잡힌 경우 직접 추가
        seen = {idx for _, idx in candidates}
        for idx in keyword_indices:
            if idx not in seen and idx < len(self._chunks):
                # 벡터 유사도 직접 계산
                vec = self._index.reconstruct(idx).reshape(1, -1)
                raw_score = float(np.dot(query_np[0], vec[0]))
                candidates.append((raw_score + name_boost, idx))

        # 점수 높은 순 정렬 → top_k
        candidates.sort(key=lambda x: x[0], reverse=True)

        results: list[SearchResult] = []
        for score, idx in candidates[:top_k]:
            meta = self._meta[idx] if idx < len(self._meta) else {}
            results.append(
                SearchResult(
                    score=score,
                    chunk=self._chunks[idx],
                    medication_id=meta.get("medication_id", ""),
                    name=meta.get("name", ""),
                    category=meta.get("category", ""),
                    source=meta.get("source", ""),
                )
            )

        return results
