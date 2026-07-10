from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ActivityLog, Branch, Customer, Expense, Product, ProductStock, Purchase, Return, Sale
from .permissions import IsPosMember
from .serializers import (
    ActivityLogSerializer, BranchSerializer, CustomerSerializer, ExpenseSerializer,
    ProductSerializer, ProductStockSerializer, PurchaseSerializer, ReturnSerializer, SaleSerializer,
)

MUTABLE_RESOURCES = {
    "branches": (Branch, BranchSerializer),
    "products": (Product, ProductSerializer),
    "productStock": (ProductStock, ProductStockSerializer),
    "customers": (Customer, CustomerSerializer),
}

LEDGER_RESOURCES = {
    "sales": (Sale, SaleSerializer),
    "returns": (Return, ReturnSerializer),
    "purchases": (Purchase, PurchaseSerializer),
    "expenses": (Expense, ExpenseSerializer),
    "logs": (ActivityLog, ActivityLogSerializer),
}

ALL_RESOURCES = {**MUTABLE_RESOURCES, **LEDGER_RESOURCES}


class SyncPullView(APIView):
    """GET /api/v1/pos/sync/pull/?since=<iso8601>
       Returns every tenant record changed since `since` (omit for a full
       pull) across all resource types, plus `server_time` to store as the
       next `since` cursor."""

    permission_classes = [IsAuthenticated, IsPosMember]

    def get(self, request):
        since_param = request.query_params.get("since")
        since_dt = parse_datetime(since_param) if since_param else None
        tenant = request.user.posprofile.tenant
        server_time = timezone.now()

        resources = {}
        for name, (model, serializer_cls) in ALL_RESOURCES.items():
            timestamp_field = "timestamp" if model is ActivityLog else "updated_at"
            qs = model.objects.filter(tenant=tenant)
            if since_dt:
                qs = qs.filter(**{f"{timestamp_field}__gt": since_dt})
            if name in ("sales", "returns"):
                qs = qs.prefetch_related("items")
            resources[name] = serializer_cls(qs.order_by(timestamp_field), many=True).data

        return Response({"server_time": server_time.isoformat(), "resources": resources})


class SyncPushView(APIView):
    """POST /api/v1/pos/sync/push/
       Body: {"changes": {"products": [...], "sales": [...], ...}}

       Mutable resources: last-write-wins by `updated_at`, rejected pushes
       come back in `conflicts` with the server's current version.
       Ledger resources: create-only, idempotent by id."""

    permission_classes = [IsAuthenticated, IsPosMember]

    @transaction.atomic
    def post(self, request):
        tenant = request.user.posprofile.tenant
        changes = request.data.get("changes", {})
        applied = {}
        conflicts = {}

        for name, (model, serializer_cls) in MUTABLE_RESOURCES.items():
            applied[name] = []
            conflicts[name] = []
            for record in changes.get(name, []):
                record_id = record.get("id")
                if not record_id:
                    continue

                existing = model.objects.filter(tenant=tenant, id=record_id).first()
                incoming_updated_at = (
                    parse_datetime(record["updated_at"]) if record.get("updated_at") else None
                )

                if existing and incoming_updated_at and existing.updated_at > incoming_updated_at:
                    conflicts[name].append({"id": str(record_id), "server_version": serializer_cls(existing).data})
                    continue

                serializer = serializer_cls(existing, data=record, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save(tenant=tenant, id=record_id)
                applied[name].append(str(record_id))

        for name, (model, serializer_cls) in LEDGER_RESOURCES.items():
            applied[name] = []
            for record in changes.get(name, []):
                record_id = record.get("id")
                if not record_id or model.objects.filter(tenant=tenant, id=record_id).exists():
                    continue  # already synced (or malformed) — skip quietly, idempotent

                serializer = serializer_cls(data=record)
                serializer.is_valid(raise_exception=True)
                extra = {"tenant": tenant, "id": record_id}
                if hasattr(model, "created_by"):
                    extra["created_by"] = request.user
                instance = serializer.save(**extra)
                applied[name].append(str(record_id))
                _apply_stock_delta(name, instance)

        return Response({
            "server_time": timezone.now().isoformat(),
            "applied": applied,
            "conflicts": conflicts,
        })


def _apply_stock_delta(resource_name, instance):
    """Sales/returns/purchases move stock via delta, never absolute
    overwrite. `python manage.py reconcile_stock` recomputes from scratch
    if you ever want to double-check nothing's drifted."""
    if resource_name == "sales":
        for item in instance.items.select_related("product"):
            if not item.product.unlimited:
                _adjust_stock(instance.tenant_id, item.product_id, instance.branch_id, -item.qty)
    elif resource_name == "returns":
        for item in instance.items.select_related("product"):
            if not item.product.unlimited:
                _adjust_stock(instance.tenant_id, item.product_id, instance.branch_id, item.qty)
    elif resource_name == "purchases":
        if not instance.product.unlimited:
            _adjust_stock(instance.tenant_id, instance.product_id, instance.branch_id, instance.qty)


def _adjust_stock(tenant_id, product_id, branch_id, delta):
    stock, _ = ProductStock.objects.get_or_create(
        tenant_id=tenant_id, product_id=product_id, branch_id=branch_id, defaults={"quantity": 0}
    )
    ProductStock.objects.filter(pk=stock.pk).update(quantity=F("quantity") + delta)
