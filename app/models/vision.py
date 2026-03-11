from enum import StrEnum

from tortoise import fields, models


class ReviewPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class QueueStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ReviewStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"


class RetrainBucket(StrEnum):
    DETECT = "detect"
    CLASSIFY = "classify"
    BOTH = "both"
    NONE = "none"


class VisionSample(models.Model):
    id = fields.BigIntField(primary_key=True)
    sample_id = fields.CharField(max_length=64, unique=True)
    request_endpoint = fields.CharField(max_length=100, default="/api/vision/identify")
    source_type = fields.CharField(max_length=30, default="user_upload")
    original_image_path = fields.CharField(max_length=500, null=True)
    content_type = fields.CharField(max_length=100, null=True)
    image_size_bytes = fields.IntField(default=0)
    success = fields.BooleanField(default=False)
    error_code = fields.CharField(max_length=100, null=True)
    predicted_candidates_json = fields.JSONField(default=list)
    top1_medication_id = fields.CharField(max_length=100, null=True)
    top1_confidence = fields.FloatField(null=True)
    detection_boxes_json = fields.JSONField(default=list)
    raw_detections_json = fields.JSONField(default=list)
    model_version_detect = fields.CharField(max_length=500, null=True)
    model_version_classify = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "vision_samples"
        indexes = (
            ("created_at",),
            ("success", "error_code"),
            ("top1_medication_id",),
        )


class VisionReviewQueue(models.Model):
    id = fields.BigIntField(primary_key=True)
    sample_id = fields.CharField(max_length=64, unique=True)
    review_priority = fields.CharEnumField(enum_type=ReviewPriority, default=ReviewPriority.P3)
    review_reason_codes_json = fields.JSONField(default=list)
    review_status = fields.CharEnumField(enum_type=QueueStatus, default=QueueStatus.PENDING)
    generated_at = fields.DatetimeField(auto_now_add=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "vision_review_queue"
        indexes = (
            ("review_status", "review_priority", "generated_at"),
            ("generated_at",),
        )


class VisionReviewResult(models.Model):
    id = fields.BigIntField(primary_key=True)
    sample_id = fields.CharField(max_length=64, unique=True)
    review_status = fields.CharEnumField(enum_type=ReviewStatus)
    ground_truth_medication_id = fields.CharField(max_length=100, null=True)
    retrain_eligible = fields.BooleanField(default=False)
    retrain_bucket = fields.CharEnumField(enum_type=RetrainBucket, default=RetrainBucket.NONE)
    reviewer = fields.CharField(max_length=100)
    reviewed_at = fields.DatetimeField()
    decision_reason_codes_json = fields.JSONField(default=list)
    queue_reason_codes_json = fields.JSONField(default=list)
    review_note = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "vision_review_results"
        indexes = (
            ("review_status", "reviewed_at"),
            ("retrain_eligible", "retrain_bucket", "reviewed_at"),
            ("reviewed_at",),
        )
