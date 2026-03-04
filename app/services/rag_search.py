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

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """쿼리 텍스트로 FAISS 검색을 수행합니다.

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

        # FAISS 검색 (Inner Product → cosine similarity)
        scores, indices = self._index.search(query_np, top_k)

        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0 or idx >= len(self._chunks):
                continue
            meta = self._meta[idx] if idx < len(self._meta) else {}
            results.append(
                SearchResult(
                    score=float(score),
                    chunk=self._chunks[idx],
                    medication_id=meta.get("medication_id", ""),
                    name=meta.get("name", ""),
                    category=meta.get("category", ""),
                    source=meta.get("source", ""),
                )
            )

        return results
