from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `drug_references` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `medication_id` VARCHAR(100) NOT NULL UNIQUE,
    `drug_name` VARCHAR(255),
    `company_name` VARCHAR(255),
    `efficacy_text` LONGTEXT,
    `dosage_text` LONGTEXT,
    `precautions_text` LONGTEXT,
    `warnings_text` LONGTEXT,
    `interactions_text` LONGTEXT,
    `side_effects_text` LONGTEXT,
    `storage_text` LONGTEXT,
    `source` VARCHAR(50),
    `source_item_seq` VARCHAR(100),
    `raw_payload_json` JSON NOT NULL,
    `last_synced_at` DATETIME(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY `idx_drug_refere_drug_na_d9741e` (`drug_name`),
    KEY `idx_drug_refere_source__1fcd87` (`source_item_seq`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `drug_references`;"""


MODELS_STATE = (
    "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"
    "drkCjLCFzzkAI1MgJ3oAO7+wjcy98njPxG"
)
