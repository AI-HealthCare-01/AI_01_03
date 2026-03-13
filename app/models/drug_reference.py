from tortoise import fields, models


class DrugReference(models.Model):
    id = fields.BigIntField(primary_key=True)
    medication_id = fields.CharField(max_length=100, unique=True)
    drug_name = fields.CharField(max_length=255, null=True)
    company_name = fields.CharField(max_length=255, null=True)
    efficacy_text = fields.TextField(null=True)
    dosage_text = fields.TextField(null=True)
    precautions_text = fields.TextField(null=True)
    warnings_text = fields.TextField(null=True)
    interactions_text = fields.TextField(null=True)
    side_effects_text = fields.TextField(null=True)
    storage_text = fields.TextField(null=True)
    source = fields.CharField(max_length=50, null=True)
    source_item_seq = fields.CharField(max_length=100, null=True)
    raw_payload_json = fields.JSONField(default=dict)
    last_synced_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "drug_references"
        indexes = (
            ("drug_name",),
            ("source_item_seq",),
        )
