import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    """A business using the POS. Every POS model below carries a `tenant`
    FK and every queryset must filter by it — that's the entire multi-
    tenant boundary, so it's worth being paranoid about applying it
    everywhere (see TenantScopedQuerysetMixin in permissions.py)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PosProfile(models.Model):
    """
    Extends the existing app.User with POS-specific fields, rather than
    touching that model directly — app.User already has its own `role`
    field (Admin/Staff) used elsewhere in this project, so POS roles
    (admin/manager/sales) live here instead to avoid any collision.

    One user -> one POS tenant. Adding a second staff member to an
    existing tenant isn't self-serve yet (no invite-by-email flow) — an
    existing admin adds them as a roster entry via the frontend's Settings
    tab today; giving that roster entry actual login access is the next
    piece to build.
    """

    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_SALES = "sales"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_SALES, "Sales"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posprofile")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_SALES)
    branch_id = models.UUIDField(null=True, blank=True)
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True, db_index=True)

    def __str__(self):
        return f"{self.user} @ {self.tenant} ({self.role})"


def default_invite_expiry():
    return timezone.now() + timedelta(days=7)


def generate_invite_token():
    return secrets.token_urlsafe(32)


class PosInvite(models.Model):
    """An outstanding invitation for someone to join an existing tenant with
    a given role/branch. Created by an admin (POST /auth/invite/); the
    recipient follows a link containing `token` to set their own password
    and, on success, gets a real User + PosProfile (POST /auth/invite/accept/).
    No email is sent server-side yet — the admin shares the link directly
    (matches the existing WhatsApp-share pattern already used for receipts)."""

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REVOKED, "Revoked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=PosProfile.ROLE_CHOICES, default=PosProfile.ROLE_SALES)
    branch_id = models.UUIDField(null=True, blank=True)
    token = models.CharField(max_length=64, unique=True, db_index=True, default=generate_invite_token)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_invite_expiry)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "email"])]

    def __str__(self):
        return f"invite {self.email} -> {self.tenant} ({self.status})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class TenantScopedModel(models.Model):
    """Client-generated UUID primary keys are what make offline-first sync
    work: a sale rung up with no signal gets its final ID immediately, so
    there's no server-assigned-ID renumbering to reconcile once it syncs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class Branch(TenantScopedModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Product(TenantScopedModel):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unlimited = models.BooleanField(default=False, help_text="e.g. airtime — never runs out")

    class Meta:
        indexes = [models.Index(fields=["tenant", "category"])]

    def __str__(self):
        return self.name


class ProductStock(TenantScopedModel):
    """Per-branch stock level — a CACHE, not the source of truth. The real
    stock position is always derivable by replaying Purchase (+) and
    Sale/Return (-/+) ledger rows; `python manage.py reconcile_stock`
    recomputes this table from scratch. Direct edits here (a stocktake
    correction) are the one place last-write-wins applies to stock —
    everyday sales/purchases move it via delta, never overwrite."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_levels")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="stock_levels")
    quantity = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "branch"], name="unique_product_branch_stock")
        ]


class Customer(TenantScopedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name

class Sale(TenantScopedModel):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sales")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales")
    customer_name_snapshot = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    occurred_at = models.DateTimeField(help_text="Client-side timestamp of when the sale actually happened")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        indexes = [models.Index(fields=["tenant", "branch", "occurred_at"])]


class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    name_snapshot = models.CharField(max_length=255)
    price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.IntegerField()


class Return(TenantScopedModel):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="returns")
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="returns")
    customer_name_snapshot = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=500, blank=True)
    occurred_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")


class ReturnItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_record = models.ForeignKey(Return, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    name_snapshot = models.CharField(max_length=255)
    price_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.IntegerField()


class Purchase(TenantScopedModel):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="purchases")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchases")
    product_name_snapshot = models.CharField(max_length=255)
    qty = models.IntegerField()
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    occurred_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")


class Expense(TenantScopedModel):
    category = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=500, blank=True)
    occurred_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")


class ActivityLog(TenantScopedModel):
    TYPE_CHOICES = [
        ("sale", "Sale"), ("return", "Return"), ("product", "Product"),
        ("customer", "Customer"), ("purchase", "Purchase"), ("expense", "Expense"),
        ("settings", "Settings"), ("sync", "Sync"),
    ]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    timestamp = models.DateTimeField(auto_now_add=True)
