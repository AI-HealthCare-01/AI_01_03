from tortoise import fields, models


class MedicationSchedule(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="medication_schedules", on_delete=fields.CASCADE)
    prescription_item = fields.ForeignKeyField(
        "models.PrescriptionItem",
        related_name="schedules",
        on_delete=fields.CASCADE,
    )
    day_offset = fields.IntField(default=0)
    time_slot = fields.CharField(max_length=20)
    scheduled_time = fields.TimeField()
    is_completed = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "medication_schedules"
        indexes = (
            ("user_id", "created_at", "id"),
            ("user_id", "is_completed"),
            ("prescription_item_id",),
        )
