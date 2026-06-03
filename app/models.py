from django.db import models
from django.contrib.auth.models import AbstractUser

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension


class User(AbstractUser):
    role = models.CharField(
        max_length=5, choices=[("Admin", "admin"), ("Staff", "staff")], default="admin"
    )


class Category(models.Model):
    name = models.CharField(max_length=25)


class HsCodeFile(models.Model):
    hs_code_file = models.FileField(upload_to="hs_code")


class HsCode(models.Model):
    hs_code_file = models.ForeignKey(HsCodeFile, on_delete=models.CASCADE)
    hs_code = models.CharField(max_length=20)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["hs_code"], name="unique_hs_code")
        ]
        indexes = [
            GinIndex(
                fields=["hs_code"],
                opclasses=["gin_trgm_ops"],
                name="hscode_hs_code_trgm_idx",
            ),
            GinIndex(
                fields=["description"],
                opclasses=["gin_trgm_ops"],
                name="hscode_description_trgm_idx",
            ),
        ]
