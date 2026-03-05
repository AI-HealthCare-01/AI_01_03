import json, sys
sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open('data/knowledge_base.json', encoding='utf-8'))
meds = data['medications']
filled = sum(1 for m in meds if m.get('efficacy'))
empty = sum(1 for m in meds if not m.get('efficacy'))
print(f'총: {len(meds)}건')
print(f'데이터 있음: {filled}건')
print(f'빈 것: {empty}건')
