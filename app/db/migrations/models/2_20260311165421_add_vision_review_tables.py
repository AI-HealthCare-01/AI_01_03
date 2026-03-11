from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `vision_review_queue` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `sample_id` VARCHAR(64) NOT NULL UNIQUE,
    `review_priority` VARCHAR(2) NOT NULL COMMENT 'P0: P0\nP1: P1\nP2: P2\nP3: P3\nP4: P4' DEFAULT 'P3',
    `review_reason_codes_json` JSON NOT NULL,
    `review_status` VARCHAR(11) NOT NULL COMMENT 'PENDING: pending\nIN_PROGRESS: in_progress\nDONE: done' DEFAULT 'pending',
    `generated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_vision_revi_review__a894bd` (`review_status`, `review_priority`, `generated_at`),
    KEY `idx_vision_revi_generat_85c735` (`generated_at`)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `vision_review_results` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `sample_id` VARCHAR(64) NOT NULL UNIQUE,
    `review_status` VARCHAR(10) NOT NULL COMMENT 'APPROVED: approved\nREJECTED: rejected\nNEEDS_INFO: needs_info',
    `ground_truth_medication_id` VARCHAR(100),
    `retrain_eligible` BOOL NOT NULL DEFAULT 0,
    `retrain_bucket` VARCHAR(8) NOT NULL COMMENT 'DETECT: detect\nCLASSIFY: classify\nBOTH: both\nNONE: none' DEFAULT 'none',
    `reviewer` VARCHAR(100) NOT NULL,
    `reviewed_at` DATETIME(6) NOT NULL,
    `decision_reason_codes_json` JSON NOT NULL,
    `queue_reason_codes_json` JSON NOT NULL,
    `review_note` LONGTEXT,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_vision_revi_review__29ca47` (`review_status`, `reviewed_at`),
    KEY `idx_vision_revi_retrain_beaee9` (`retrain_eligible`, `retrain_bucket`, `reviewed_at`),
    KEY `idx_vision_revi_reviewe_db0c4d` (`reviewed_at`)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `vision_samples` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `sample_id` VARCHAR(64) NOT NULL UNIQUE,
    `request_endpoint` VARCHAR(100) NOT NULL DEFAULT '/api/vision/identify',
    `source_type` VARCHAR(30) NOT NULL DEFAULT 'user_upload',
    `original_image_path` VARCHAR(500),
    `content_type` VARCHAR(100),
    `image_size_bytes` INT NOT NULL DEFAULT 0,
    `success` BOOL NOT NULL DEFAULT 0,
    `error_code` VARCHAR(100),
    `predicted_candidates_json` JSON NOT NULL,
    `top1_medication_id` VARCHAR(100),
    `top1_confidence` DOUBLE,
    `detection_boxes_json` JSON NOT NULL,
    `raw_detections_json` JSON NOT NULL,
    `model_version_detect` VARCHAR(500),
    `model_version_classify` VARCHAR(500),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_vision_samp_created_c34df0` (`created_at`),
    KEY `idx_vision_samp_success_c98279` (`success`, `error_code`),
    KEY `idx_vision_samp_top1_me_f8f175` (`top1_medication_id`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `vision_samples`;
        DROP TABLE IF EXISTS `vision_review_queue`;
        DROP TABLE IF EXISTS `vision_review_results`;"""


MODELS_STATE = (
    "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"
)
