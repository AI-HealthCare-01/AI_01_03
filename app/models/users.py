from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    email = fields.CharField(max_length=40, unique=True)
    hashed_password = fields.CharField(max_length=128, null=True)
    name = fields.CharField(max_length=20)
    gender = fields.CharEnumField(enum_type=Gender, null=True)
    birthday = fields.DateField(null=True)
    phone_number = fields.CharField(max_length=15, null=True)
    provider = fields.CharField(max_length=20, default="local")
    sns_id = fields.CharField(max_length=100, null=True)
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
