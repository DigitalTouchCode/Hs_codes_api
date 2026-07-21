import uuid

import django.db.models.deletion
import pos.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PosInvite",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[("admin", "Admin"), ("manager", "Manager"), ("sales", "Sales")],
                        default="sales",
                        max_length=20,
                    ),
                ),
                ("branch_id", models.UUIDField(blank=True, null=True)),
                (
                    "token",
                    models.CharField(default=pos.models.generate_invite_token, max_length=64, unique=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("accepted", "Accepted"), ("revoked", "Revoked")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(default=pos.models.default_invite_expiry)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites", to="pos.tenant",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="posinvite",
            index=models.Index(fields=["tenant", "email"], name="pos_posinvite_tenant_email_idx"),
        ),
    ]
