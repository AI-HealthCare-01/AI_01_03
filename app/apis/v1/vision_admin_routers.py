from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from tortoise.transactions import in_transaction

from app.dependencies.security import get_admin_user
from app.dtos.vision_admin import (
    VisionAdminReviewQueueItem,
    VisionAdminReviewQueuePayload,
    VisionAdminReviewQueueResponse,
    VisionAdminReviewResultPayload,
    VisionAdminReviewResultUpsertRequest,
    VisionAdminReviewResultUpsertResponse,
    VisionAdminSampleDetailResponse,
    VisionAdminSamplePayload,
)
from app.models.users import User
from app.models.vision import QueueStatus, VisionReviewQueue, VisionReviewResult, VisionSample

vision_admin_router = APIRouter(prefix="/admin/vision", tags=["VisionAdmin"])


def _safe_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


@vision_admin_router.get("/review-queue", response_model=VisionAdminReviewQueueResponse)
async def get_review_queue(
    _: Annotated[User, Depends(get_admin_user)],
    review_priority: Annotated[str | None, Query()] = None,
    review_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VisionAdminReviewQueueResponse:
    queue_qs = VisionReviewQueue.all()
    if review_priority:
        queue_qs = queue_qs.filter(review_priority=review_priority)
    if review_status:
        queue_qs = queue_qs.filter(review_status=review_status)

    total = await queue_qs.count()
    queue_rows = await queue_qs.order_by("review_priority", "-generated_at").offset(offset).limit(limit)

    sample_ids = [item.sample_id for item in queue_rows]
    sample_map = {item.sample_id: item for item in await VisionSample.filter(sample_id__in=sample_ids)}

    items: list[VisionAdminReviewQueueItem] = []
    for queue_item in queue_rows:
        sample = sample_map.get(queue_item.sample_id)
        items.append(
            VisionAdminReviewQueueItem(
                sample_id=queue_item.sample_id,
                review_priority=str(queue_item.review_priority),
                review_status=str(queue_item.review_status),
                review_reason_codes=_safe_str_list(queue_item.review_reason_codes_json),
                error_code=sample.error_code if sample else None,
                top1_medication_id=sample.top1_medication_id if sample else None,
                top1_confidence=sample.top1_confidence if sample else None,
                original_image_path=sample.original_image_path if sample else None,
                created_at=(sample.created_at if sample else queue_item.created_at),
            )
        )

    return VisionAdminReviewQueueResponse(items=items, total=total)


@vision_admin_router.get("/samples/{sample_id}", response_model=VisionAdminSampleDetailResponse)
async def get_sample_detail(
    sample_id: str,
    _: Annotated[User, Depends(get_admin_user)],
) -> VisionAdminSampleDetailResponse:
    sample = await VisionSample.get_or_none(sample_id=sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision sample not found")

    queue = await VisionReviewQueue.get_or_none(sample_id=sample_id)
    review_result = await VisionReviewResult.get_or_none(sample_id=sample_id)

    sample_payload = VisionAdminSamplePayload(
        sample_id=sample.sample_id,
        request_endpoint=sample.request_endpoint,
        source_type=sample.source_type,
        original_image_path=sample.original_image_path,
        content_type=sample.content_type,
        image_size_bytes=sample.image_size_bytes,
        success=sample.success,
        error_code=sample.error_code,
        predicted_candidates=sample.predicted_candidates_json or [],
        top1_medication_id=sample.top1_medication_id,
        top1_confidence=sample.top1_confidence,
        detection_boxes=sample.detection_boxes_json or [],
        raw_detections=sample.raw_detections_json or [],
        model_version_detect=sample.model_version_detect,
        model_version_classify=sample.model_version_classify,
        created_at=sample.created_at,
        updated_at=sample.updated_at,
    )

    queue_payload = None
    if queue is not None:
        queue_payload = VisionAdminReviewQueuePayload(
            sample_id=queue.sample_id,
            review_priority=str(queue.review_priority),
            review_status=str(queue.review_status),
            review_reason_codes=_safe_str_list(queue.review_reason_codes_json),
            generated_at=queue.generated_at,
            created_at=queue.created_at,
            updated_at=queue.updated_at,
        )

    review_result_payload = None
    if review_result is not None:
        review_result_payload = VisionAdminReviewResultPayload(
            sample_id=review_result.sample_id,
            review_status=str(review_result.review_status),
            ground_truth_medication_id=review_result.ground_truth_medication_id,
            retrain_eligible=review_result.retrain_eligible,
            retrain_bucket=str(review_result.retrain_bucket),
            reviewer=review_result.reviewer,
            reviewed_at=review_result.reviewed_at,
            decision_reason_codes=_safe_str_list(review_result.decision_reason_codes_json),
            queue_reason_codes=_safe_str_list(review_result.queue_reason_codes_json),
            review_note=review_result.review_note,
            created_at=review_result.created_at,
            updated_at=review_result.updated_at,
        )

    return VisionAdminSampleDetailResponse(
        sample=sample_payload,
        queue=queue_payload,
        review_result=review_result_payload,
    )


@vision_admin_router.put("/review-results/{sample_id}", response_model=VisionAdminReviewResultUpsertResponse)
async def upsert_review_result(
    sample_id: str,
    body: VisionAdminReviewResultUpsertRequest,
    admin_user: Annotated[User, Depends(get_admin_user)],
) -> VisionAdminReviewResultUpsertResponse:
    sample = await VisionSample.get_or_none(sample_id=sample_id)
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision sample not found")

    reviewed_at = datetime.now()
    reviewer = (admin_user.email or str(admin_user.id)).strip()

    async with in_transaction() as connection:
        queue_row = await VisionReviewQueue.filter(sample_id=sample_id).using_db(connection).first()
        queue_reason_codes = _safe_str_list(queue_row.review_reason_codes_json) if queue_row else []

        review_result = await VisionReviewResult.filter(sample_id=sample_id).using_db(connection).first()
        if review_result is None:
            review_result = await VisionReviewResult.create(
                sample_id=sample_id,
                review_status=body.review_status,
                ground_truth_medication_id=body.ground_truth_medication_id,
                retrain_eligible=body.retrain_eligible,
                retrain_bucket=body.retrain_bucket,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
                decision_reason_codes_json=body.decision_reason_codes,
                queue_reason_codes_json=queue_reason_codes,
                review_note=body.review_note,
                using_db=connection,
            )
        else:
            review_result.review_status = body.review_status
            review_result.ground_truth_medication_id = body.ground_truth_medication_id
            review_result.retrain_eligible = body.retrain_eligible
            review_result.retrain_bucket = body.retrain_bucket
            review_result.reviewer = reviewer
            review_result.reviewed_at = reviewed_at
            review_result.decision_reason_codes_json = body.decision_reason_codes
            review_result.queue_reason_codes_json = queue_reason_codes
            review_result.review_note = body.review_note
            await review_result.save(using_db=connection)

        if queue_row is not None:
            queue_row.review_status = QueueStatus.DONE
            await queue_row.save(using_db=connection)

    return VisionAdminReviewResultUpsertResponse(
        sample_id=sample_id,
        review_status=body.review_status,
        retrain_eligible=body.retrain_eligible,
        retrain_bucket=body.retrain_bucket,
        reviewed_at=reviewed_at,
    )
