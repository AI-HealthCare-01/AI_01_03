from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `prescriptions` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `source_text` LONGTEXT NOT NULL,
    `is_user_confirmed` BOOL NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_prescrip_users_75d98828` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_prescriptio_user_id_42c042` (`user_id`, `created_at`)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `prescription_items` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(100) NOT NULL,
    `dose_text` VARCHAR(100) NOT NULL,
    `medication_id` VARCHAR(50),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `prescription_id` BIGINT NOT NULL,
    CONSTRAINT `fk_prescrip_prescrip_7cb46274` FOREIGN KEY (`prescription_id`) REFERENCES `prescriptions` (`id`) ON DELETE CASCADE,
    KEY `idx_prescriptio_prescri_9181a8` (`prescription_id`),
    KEY `idx_prescriptio_medicat_805a46` (`medication_id`)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `medication_schedules` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `day_offset` INT NOT NULL DEFAULT 0,
    `time_slot` VARCHAR(20) NOT NULL,
    `scheduled_time` TIME(6) NOT NULL,
    `is_completed` BOOL NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `prescription_item_id` BIGINT NOT NULL,
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_medicati_prescrip_c96016a7` FOREIGN KEY (`prescription_item_id`) REFERENCES `prescription_items` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_medicati_users_34f74703` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_medication__user_id_d78c3b` (`user_id`, `created_at`, `id`),
    KEY `idx_medication__user_id_1dbb1f` (`user_id`, `is_completed`),
    KEY `idx_medication__prescri_9562c7` (`prescription_item_id`)
) CHARACTER SET utf8mb4;
        ALTER TABLE `users` ADD `provider` VARCHAR(20) NOT NULL DEFAULT 'local';
        ALTER TABLE `users` ADD `sns_id` VARCHAR(100);
        ALTER TABLE `users` MODIFY COLUMN `gender` VARCHAR(6) COMMENT 'MALE: MALE\nFEMALE: FEMALE';
        ALTER TABLE `users` MODIFY COLUMN `birthday` DATE;
        ALTER TABLE `users` MODIFY COLUMN `phone_number` VARCHAR(15);
        ALTER TABLE `users` MODIFY COLUMN `phone_number` VARCHAR(15);
        ALTER TABLE `users` MODIFY COLUMN `hashed_password` VARCHAR(128);
        ALTER TABLE `users` ADD UNIQUE INDEX `email` (`email`);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` DROP INDEX `email`;
        ALTER TABLE `users` DROP COLUMN `provider`;
        ALTER TABLE `users` DROP COLUMN `sns_id`;
        ALTER TABLE `users` MODIFY COLUMN `gender` VARCHAR(6) NOT NULL COMMENT 'MALE: MALE\nFEMALE: FEMALE';
        ALTER TABLE `users` MODIFY COLUMN `birthday` DATE NOT NULL;
        ALTER TABLE `users` MODIFY COLUMN `phone_number` VARCHAR(11) NOT NULL;
        ALTER TABLE `users` MODIFY COLUMN `phone_number` VARCHAR(11) NOT NULL;
        ALTER TABLE `users` MODIFY COLUMN `hashed_password` VARCHAR(128) NOT NULL;
        DROP TABLE IF EXISTS `prescriptions`;
        DROP TABLE IF EXISTS `medication_schedules`;
        DROP TABLE IF EXISTS `prescription_items`;"""


MODELS_STATE = (
    "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"
    "byZu6s3E2X+PxcsU"
)
