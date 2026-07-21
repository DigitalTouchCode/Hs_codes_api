from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from rest_framework import serializers

from .models import (
    ActivityLog, Branch, Customer, Expense, PosInvite, PosProfile, Product, ProductStock,
    Purchase, Return, ReturnItem, Sale, SaleItem, Tenant,
)

User = get_user_model()


def unique_slug_for(name):
    base_slug = slugify(name) or "business"
    slug = base_slug
    i = 1
    while Tenant.objects.filter(slug=slug).exists():
        i += 1
        slug = f"{base_slug}-{i}"
    return slug


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class SignupSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def create(self, validated_data):
        tenant = Tenant.objects.create(
            name=validated_data["business_name"], slug=unique_slug_for(validated_data["business_name"])
        )
        # username=email works fine here: Django's default username validator
        # allows @ and . , so no schema change needed on the existing User model.
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["name"],
        )
        PosProfile.objects.create(user=user, tenant=tenant, role=PosProfile.ROLE_ADMIN)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class GoogleAuthSerializer(serializers.Serializer):
    # Matches the field name the existing news.GoogleAuthView already uses
    # for the credential from Google Identity Services, for consistency.
    credential = serializers.CharField()
    business_name = serializers.CharField(required=False, allow_blank=True)


class PosProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.first_name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = PosProfile
        fields = ["email", "name", "role", "tenant", "tenant_name", "branch_id"]


# ---------------------------------------------------------------------------
# Invites & roster management
# ---------------------------------------------------------------------------

class InviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=PosProfile.ROLE_CHOICES)
    branch = serializers.UUIDField(source="branch_id", required=False, allow_null=True)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class InvitePublicSerializer(serializers.Serializer):
    """What an unauthenticated invite link shows before the person has set
    a password — enough to say "you're joining X as a Y", nothing sensitive."""

    email = serializers.EmailField()
    role = serializers.CharField()
    business_name = serializers.CharField(source="tenant.name")
    branch_name = serializers.SerializerMethodField()

    def get_branch_name(self, invite):
        if not invite.branch_id:
            return None
        branch = Branch.objects.filter(id=invite.branch_id, tenant=invite.tenant, is_deleted=False).first()
        return branch.name if branch else None


class InviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, validators=[validate_password])


class DirectUserCreateSerializer(serializers.Serializer):
    """Admin creates a teammate's login directly, password included —
    the alternative to inviting by email when the admin already knows
    the person and wants them able to log in right away."""

    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(choices=PosProfile.ROLE_CHOICES)
    branch = serializers.UUIDField(source="branch_id", required=False, allow_null=True)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value


class RosterEntrySerializer(serializers.Serializer):
    """Unified read model for Settings > Users & roles: real PosProfiles
    (status=active) plus outstanding PosInvites (status=invited), so two
    admins on different devices see the same roster."""

    id = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    branch_id = serializers.UUIDField(allow_null=True)
    status = serializers.CharField()


# ---------------------------------------------------------------------------
# POS data
# ---------------------------------------------------------------------------

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "updated_at", "is_deleted"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "sku", "category", "price", "cost", "unlimited", "updated_at", "is_deleted"]


class ProductStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStock
        fields = ["id", "product", "branch", "quantity", "updated_at", "is_deleted"]


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "updated_at", "is_deleted"]


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ["id", "product", "name_snapshot", "price_snapshot", "qty"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)

    class Meta:
        model = Sale
        fields = [
            "id", "branch", "customer", "customer_name_snapshot",
            "total", "occurred_at", "created_by", "items", "updated_at", "is_deleted",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        sale = Sale.objects.create(**validated_data)
        SaleItem.objects.bulk_create([SaleItem(sale=sale, **item) for item in items_data])
        return sale


class ReturnItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnItem
        fields = ["id", "product", "name_snapshot", "price_snapshot", "qty"]


class ReturnSerializer(serializers.ModelSerializer):
    items = ReturnItemSerializer(many=True)

    class Meta:
        model = Return
        fields = [
            "id", "branch", "sale", "customer_name_snapshot", "total",
            "reason", "occurred_at", "created_by", "items", "updated_at", "is_deleted",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        return_record = Return.objects.create(**validated_data)
        ReturnItem.objects.bulk_create(
            [ReturnItem(return_record=return_record, **item) for item in items_data]
        )
        return return_record


class PurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Purchase
        fields = [
            "id", "branch", "product", "product_name_snapshot", "qty",
            "cost", "total", "occurred_at", "created_by", "updated_at", "is_deleted",
        ]


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ["id", "category", "amount", "note", "occurred_at", "created_by", "updated_at", "is_deleted"]


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ["id", "type", "message", "actor", "timestamp"]
