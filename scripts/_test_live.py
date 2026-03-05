import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

tests = [
    "키트루다 알려줘",       # 면역항암제 신약 (전문의약품)
    "엔허투 정보",           # 최신 표적항암제
    "마이암부톨 주의사항",    # 이전에 e약은요 없던 전문의약품
]

for question in tests:
    print(f"\n{'='*60}")
    print(f"질문: {question}")
    body = json.dumps({'question': question}).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:8000/api/v1/chat',
        data=body,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get('success'):
            print(f"[성공] citations: {data.get('citations')}")
            print(f"답변:\n{data.get('answer', '')[:400]}")
        else:
            print(f"[실패] {data.get('error_code')}")
    except Exception as e:
        print(f"[에러] {e}")
