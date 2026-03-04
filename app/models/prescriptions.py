from tortoise import fields, models


class Prescription(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="prescriptions", on_delete=fields.CASCADE)
    source_text = fields.TextField()
    is_user_confirmed = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "prescriptions"


class PrescriptionItem(models.Model):
    id = fields.BigIntField(primary_key=True)
    prescription = fields.ForeignKeyField("models.Prescription", related_name="items", on_delete=fields.CASCADE)
    name = fields.CharField(max_length=100)
    dose_text = fields.CharField(max_length=100)
    medication_id = fields.CharField(max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "prescription_items"
