import asyncio
import time
from app.services.prescription_flow import PrescriptionFlowService
from app.dtos.integration import OCRMedication

# Sample medications for testing
SAMPLE_MEDICATIONS = [
    OCRMedication(name="게보린", dose_text="1일 3회, 3일분"),
    OCRMedication(name="타이레놀", dose_text="1일 3회, 5일분"),
    OCRMedication(name="애드빌", dose_text="1일 2회, 7일분"),
]

async def benchmark_db_save():
    service = PrescriptionFlowService()
    user_id = 1  # Sample user ID
    source_text = "Sample prescription text"

    start_time = time.time()
    result = await service.save_prescription_with_schedules(
        user_id=user_id,
        source_text=source_text,
        medications=SAMPLE_MEDICATIONS
    )
    end_time = time.time()

    save_time = end_time - start_time
    print(f"DB save time: {save_time:.4f}s")
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(benchmark_db_save())