import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from app.services.live_drug_lookup import lookup_drug, _build_search_names

tests = ["키트루다 알려줘", "마이암부톨 주의사항", "엔허투 정보"]
for q in tests:
    names = _build_search_names(q)
    print(f"\n질문: {q}")
    print(f"  검색어 후보: {names}")
    result = lookup_drug(q)
    if result:
        ctx, name = result
        print(f"  [성공] -> {name}")
        print(f"  컨텍스트 (앞 200자): {ctx[:200]}")
    else:
        print(f"  [실패] 못 찾음")
