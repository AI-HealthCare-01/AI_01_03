import asyncio
import time
from app.services.ocr import OCRService

# Sample prescription texts for testing
SAMPLE_TEXTS = [
    "게보린 1일 3회, 3일분",
    "타이레놀정500mg(성인용) 1일 3회, 5일분",
    "애드빌정(화이자) 10T 1일 2회, 7일분",
    "우루사정 100MG (대웅) 1일 3회, 10일분",
    "부루펜정400mg 20T 1일 2회, 5일분",
]

async def benchmark_ocr_parsing():
    service = OCRService()
    results = []

    for text in SAMPLE_TEXTS:
        start_time = time.time()
        medications = service.parse_prescription_text(text)
        end_time = time.time()

        parsing_time = end_time - start_time
        results.append({
            'text': text,
            'parsing_time': parsing_time,
            'medications': [{'name': med.name, 'dose_text': med.dose_text} for med in medications]
        })
        print(f"Text: {text}")
        print(f"Parsing time: {parsing_time:.4f}s")
        print(f"Medications: {medications}")
        print("-" * 50)

    avg_time = sum(r['parsing_time'] for r in results) / len(results)
    print(f"Average parsing time: {avg_time:.4f}s")

if __name__ == "__main__":
    asyncio.run(benchmark_ocr_parsing())