import uuid
from django.db import models


class Event(models.Model):
    """
    Anonymous usage event for tools.digitaltouch.co.zw.
    No personally identifying data is stored — session_id is a random
    client-generated string (not a cookie, not tied to a login), and
    country is derived from IP at write-time then the IP is discarded.
    """

    TOOL_CHOICES = [
        ("hscodes", "HS Code Search"),
        ("vat", "VAT Calculator"),
        ("invoice", "Invoice & Quotation Maker"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool = models.CharField(max_length=32, choices=TOOL_CHOICES, db_index=True)
    action = models.CharField(
        max_length=64,
        db_index=True,
        help_text="e.g. tool_opened, hs_search_run, vat_calculated, invoice_printed",
    )
    session_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Random string generated client-side per browser session, not linked to identity.",
    )
    country = models.CharField(max_length=2, blank=True, null=True, help_text="ISO country code, derived server-side.")
    metadata = models.JSONField(blank=True, null=True, help_text="Optional small payload, e.g. {'doc_mode': 'invoice'}")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tool", "action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.tool}:{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


