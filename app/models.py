from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    role = models.CharField(
        max_length=5, choices=[("Admin", "admin"), ("Staff", "staff")], default="admin"
    )
