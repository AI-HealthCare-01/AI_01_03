"""
RAG Chat 파이프라인 응답 시간 측정 + 평가 스크립트.

사용법:
    python scripts/benchmark_chat.py                 # 전체 20개 질문
    python scripts/benchmark_chat.py --limit 5       # 5개만
    python scripts/benchmark_chat.py --rag-only       # RAG 검색만 (LLM 호출 제외)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)

# ── 평가 질문 20개 ───────────────────────────────
EVAL_QUESTIONS: list[dict] = [
    # 1~5: 특정 약품 질문 (높은 신뢰도 기대)
    {"q": "타이레놀 복용법 알려줘", "expect": "hit", "category": "specific"},
    {"q": "판콜에이 부작용이 뭐야?", "expect": "hit", "category": "specific"},
    {"q": "게보린 주의사항 알려줘", "expect": "hit", "category": "specific"},
    {"q": "훼스탈플러스 효능이 뭐야?", "expect": "hit", "category": "specific"},
    {"q": "베아제정 복용량 알려줘", "expect": "hit", "category": "specific"},
    # 6~10: 증상 기반 질문 (중간 신뢰도)
    {"q": "두통에 먹는 약 뭐가 있어?", "expect": "hit", "category": "symptom"},
    {"q": "소화불량일 때 약 추천해줘", "expect": "hit", "category": "symptom"},
    {"q": "감기약 종류 알려줘", "expect": "hit", "category": "symptom"},
    {"q": "해열제 복용법 알려줘", "expect": "hit", "category": "symptom"},
    {"q": "진통제 주의사항 알려줘", "expect": "hit", "category": "symptom"},
    # 11~15: 경계 사례 (임계값 근처)
    {"q": "이 약 먹어도 돼?", "expect": "safe", "category": "ambiguous"},
    {"q": "약국에서 파는 약 알려줘", "expect": "safe", "category": "ambiguous"},
    {"q": "알레르기 약 먹으면 졸려?", "expect": "hit", "category": "edge"},
    {"q": "임산부가 먹어도 되는 약", "expect": "hit", "category": "edge"},
    {"q": "어린이 해열제 용량", "expect": "hit", "category": "edge"},
    # 16~20: 범위 밖 질문 (안전 응답 기대)
    {"q": "오늘 날씨 어때?", "expect": "safe", "category": "out_of_scope"},
    {"q": "피자 맛있는 집 추천해줘", "expect": "safe", "category": "out_of_scope"},
    {"q": "파이썬 코드 작성해줘", "expect": "safe", "category": "out_of_scope"},
    {"q": "내 혈압이 높은데 어떻게 해야 해?", "expect": "safe", "category": "out_of_scope"},
    {"q": "암 치료법 알려줘", "expect": "safe", "category": "out_of_scope"},
]


def run_rag_only(questions: list[dict]) -> list[dict]:
    """RAG 검색만 수행하여 응답 시간과 점수를 측정합니다."""
    from app.services.rag_search import RAGSearchService

    rag = RAGSearchService.get_instance()
    results = []

    for item in questions:
        q = item["q"]
        t0 = time.perf_counter()
        search_results = rag.search(q, top_k=3)
        elapsed = time.perf_counter() - t0

        scores = [r.score for r in search_results]
        top_names = [r.name for r in search_results]
        best_score = max(scores) if scores else 0.0
        passed_threshold = best_score >= 0.45

        results.append(
            {
                "question": q,
                "category": item["category"],
                "expect": item["expect"],
                "actual": "hit" if passed_threshold else "safe",
                "correct": ("hit" if passed_threshold else "safe") == item["expect"],
                "best_score": round(best_score, 4),
                "scores": [round(s, 4) for s in scores],
                "top_results": top_names,
                "elapsed_ms": round(elapsed * 1000, 1),
            }
        )

    return results


async def run_full_pipeline(questions: list[dict]) -> list[dict]:
    """RAG + LLM 전체 파이프라인 응답 시간을 측정합니다."""
    from app.services.llm_guide import LLMGuideService
    from app.services.rag_search import RAGSearchService

    rag = RAGSearchService.get_instance()
    llm = LLMGuideService()
    results = []

    for item in questions:
        q = item["q"]
        t0 = time.perf_counter()

        # Step 1: RAG
        search_results = rag.search(q, top_k=3)
        t_rag = time.perf_counter() - t0

        scores = [r.score for r in search_results]
        best_score = max(scores) if scores else 0.0
        passed = llm.check_rag_confidence(scores)

        answer = ""
        t_llm = 0.0
        if passed:
            context = "\n\n".join(r.chunk for r in search_results)
            t1 = time.perf_counter()
            try:
                answer = await llm.generate_answer(context=context, question=q)
            except Exception as e:
                answer = f"[LLM ERROR] {e}"
            t_llm = time.perf_counter() - t1

        total = time.perf_counter() - t0
        is_safe = not passed or llm.contains_out_of_scope_marker(answer)

        results.append(
            {
                "question": q,
                "category": item["category"],
                "expect": item["expect"],
                "actual": "safe" if is_safe else "hit",
                "correct": ("safe" if is_safe else "hit") == item["expect"],
                "best_score": round(best_score, 4),
                "rag_ms": round(t_rag * 1000, 1),
                "llm_ms": round(t_llm * 1000, 1),
                "total_ms": round(total * 1000, 1),
                "answer_preview": answer[:100] if answer else "(안전 응답)",
            }
        )

    return results


def _print_result_rows(results: list[dict], mode: str) -> None:
    """개별 결과 행을 출력합니다."""
    for i, r in enumerate(results, 1):
        status = "O" if r["correct"] else "X"
        if mode == "rag-only":
            print(f"  {i:2d}. [{status}] score={r['best_score']:.4f} | {r['elapsed_ms']:6.1f}ms | {r['question']}")
            if not r["correct"]:
                print(f"      expect={r['expect']}, actual={r['actual']}, top={r['top_results'][:2]}")
        else:
            print(
                f"  {i:2d}. [{status}] score={r['best_score']:.4f} | RAG={r['rag_ms']:6.1f}ms LLM={r['llm_ms']:7.1f}ms Total={r['total_ms']:7.1f}ms"
            )
            print(f"      {r['question']}")
            if not r["correct"]:
                print(f"      expect={r['expect']}, actual={r['actual']}")


def print_report(results: list[dict], mode: str) -> None:
    """측정 결과를 테이블 형태로 출력합니다."""
    print(f"\n{'=' * 80}")
    print(f"  RAG Chat 벤치마크 결과 ({mode} mode)")
    print(f"{'=' * 80}\n")

    correct = sum(1 for r in results if r["correct"])
    total = len(results)

    _print_result_rows(results, mode)

    times = [r["elapsed_ms"] for r in results] if mode == "rag-only" else [r["total_ms"] for r in results]

    print(f"\n{'─' * 80}")
    print(f"  정확도: {correct}/{total} ({correct / total * 100:.0f}%)")
    print(
        f"  응답 시간: avg={sum(times) / len(times):.0f}ms, "
        f"min={min(times):.0f}ms, max={max(times):.0f}ms, "
        f"p95={sorted(times)[int(len(times) * 0.95)]:.0f}ms"
    )

    if mode != "rag-only":
        under_5s = sum(1 for t in times if t < 5000)
        print(f"  5초 이내 응답: {under_5s}/{total} ({under_5s / total * 100:.0f}%)")

    # 카테고리별 정확도
    categories: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"correct": 0, "total": 0}
        categories[cat]["total"] += 1
        if r["correct"]:
            categories[cat]["correct"] += 1

    print("\n  카테고리별:")
    for cat, stats in categories.items():
        print(f"    {cat:15s}: {stats['correct']}/{stats['total']}")

    print()

    # JSON 저장
    out_path = ROOT / "data" / "benchmark_results.json"
    out_path.write_text(
        json.dumps({"mode": mode, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  결과 저장: {out_path}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG Chat 벤치마크")
    parser.add_argument("--limit", type=int, default=0, help="질문 수 제한")
    parser.add_argument("--rag-only", action="store_true", help="RAG 검색만 (LLM 제외)")
    args = parser.parse_args()

    questions = EVAL_QUESTIONS[: args.limit] if args.limit else EVAL_QUESTIONS

    if args.rag_only:
        results = run_rag_only(questions)
        print_report(results, "rag-only")
    else:
        results = asyncio.run(run_full_pipeline(questions))
        print_report(results, "full-pipeline")


if __name__ == "__main__":
    main()
