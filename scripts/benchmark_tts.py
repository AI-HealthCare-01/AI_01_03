import asyncio
import time
from app.services.tts import generate_tts

# Sample texts for TTS testing
SAMPLE_TEXTS = [
    "게보린은 두통, 치통, 생리통 등 각종 통증의 진통과 해열에 사용하는 일반의약품입니다.",
    "타이레놀은 감기로 인한 발열 및 통증 완화에 사용되는 일반의약품입니다.",
    "애드빌정은 다양한 통증 및 발열 완화에 사용되는 일반의약품입니다.",
]

async def benchmark_tts():
    results = []

    for text in SAMPLE_TEXTS:
        start_time = time.time()
        audio = await generate_tts(text)
        end_time = time.time()

        tts_time = end_time - start_time
        audio_size = len(audio.getvalue())
        results.append({
            'text': text[:50] + '...' if len(text) > 50 else text,
            'tts_time': tts_time,
            'audio_size': audio_size
        })
        print(f"Text: {text[:50]}...")
        print(f"TTS time: {tts_time:.4f}s")
        print(f"Audio size: {audio_size} bytes")
        print("-" * 50)

    avg_time = sum(r['tts_time'] for r in results) / len(results)
    print(f"Average TTS time: {avg_time:.4f}s")

if __name__ == "__main__":
    asyncio.run(benchmark_tts())