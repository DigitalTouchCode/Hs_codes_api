import uuid
from django.db import models
from django.contrib.auth.models import User
from clients.models import Client


class RepairStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    RECEIVED = "received", "Received"
    DIAGNOSING = "diagnosing", "Diagnosing"
    AWAITING_PARTS = "awaiting_parts", "Awaiting Parts"
    IN_PROGRESS = "in_progress", "In Progress"
    QUALITY_CHECK = "quality_check", "Quality Check"
    READY = "ready", "Ready for Collection"
    COLLECTED = "collected", "Collected"
    CANCELLED = "cancelled", "Cancelled"


STATUS_SMS_TEMPLATES = {
    RepairStatus.BOOKED: (
        "Hi {name}, your PC repair booking (Ref: {ref}) has been received. "
        "We'll contact you shortly. Track your repair at {track_url}"
    ),
    RepairStatus.RECEIVED: (
        "Hi {name}, we've received your device (Ref: {ref}). "
        "Our technician will begin assessment soon. Track: {track_url}"
    ),
    RepairStatus.DIAGNOSING: (
        "Hi {name}, we're currently diagnosing your device (Ref: {ref}). "
        "We'll update you once we have findings. Track: {track_url}"
    ),
    RepairStatus.AWAITING_PARTS: (
        "Hi {name}, your repair (Ref: {ref}) requires parts. "
        "We'll proceed as soon as they arrive. Track: {track_url}"
    ),
    RepairStatus.IN_PROGRESS: (
        "Hi {name}, great news! Repairs are underway on your device (Ref: {ref}). "
        "Track: {track_url}"
    ),
    RepairStatus.QUALITY_CHECK: (
        "Hi {name}, your device (Ref: {ref}) is undergoing final quality checks. "
        "Almost done! Track: {track_url}"
    ),
    RepairStatus.READY: (
        "Hi {name}, your device (Ref: {ref}) is ready for collection! "
        "Please bring this reference when collecting. Track: {track_url}"
    ),
    RepairStatus.COLLECTED: (
        "Hi {name}, thank you for collecting your device (Ref: {ref}). "
        "We hope you're satisfied. Feel free to leave us a review!"
    ),
    RepairStatus.CANCELLED: (
        "Hi {name}, your repair booking (Ref: {ref}) has been cancelled. "
        "Contact us if you have any questions."
    ),
}


def repair_image_path(instance, filename):
    return f"repairs/{instance.repair.ref}/{filename}"


class Repair(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ref = models.CharField(max_length=12, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="repairs")
    device_type = models.CharField(max_length=100)
    device_brand = models.CharField(max_length=100)
    device_model = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    problem_description = models.TextField()
    status = models.CharField(
        max_length=20, choices=RepairStatus.choices, default=RepairStatus.BOOKED
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_repairs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_completion = models.DateField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} — {self.client.full_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.ref:
            self.ref = self._generate_ref()
        super().save(*args, **kwargs)

    def _generate_ref(self):
        import random
        import string
        chars = string.ascii_uppercase + string.digits
        while True:
            ref = "PCR-" + "".join(random.choices(chars, k=6))
            if not Repair.objects.filter(ref=ref).exists():
                return ref

    @property
    def total_cost(self):
        return sum(c.amount for c in self.costs.all())


class RepairImage(models.Model):
    repair = models.ForeignKey(Repair, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=repair_image_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by_staff = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.repair.ref}"


class RepairStatusLog(models.Model):
    repair = models.ForeignKey(Repair, on_delete=models.CASCADE, related_name="status_logs")
    previous_status = models.CharField(max_length=20, choices=RepairStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=RepairStatus.choices)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)
    sms_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.repair.ref}: {self.previous_status} → {self.new_status}"


class RepairNote(models.Model):
    repair = models.ForeignKey(Repair, on_delete=models.CASCADE, related_name="notes")
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Note on {self.repair.ref} by {self.added_by}"


class RepairCost(models.Model):
    repair = models.ForeignKey(Repair, on_delete=models.CASCADE, related_name="costs")
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.description} — ${self.amount} ({self.repair.ref})"
