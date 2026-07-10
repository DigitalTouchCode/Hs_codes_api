from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from pos.models import Product, ProductStock, Purchase, ReturnItem, SaleItem


class Command(BaseCommand):
    """Recomputes every ProductStock row from scratch by replaying the full
    ledger (purchases add, sales subtract, returns add back). Safe to run
    anytime — good candidate for a nightly Celery beat task alongside the
    existing news push-notification tasks.

        python manage.py reconcile_stock
        python manage.py reconcile_stock --tenant <tenant-uuid>
    """

    help = "Recompute ProductStock from the sales/purchases/returns ledger."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, default=None, help="Limit to a single tenant UUID")

    def handle(self, *args, **options):
        tenant_id = options.get("tenant")
        totals = defaultdict(int)

        purchases = Purchase.objects.filter(is_deleted=False)
        sale_items = SaleItem.objects.filter(sale__is_deleted=False).select_related("sale")
        return_items = ReturnItem.objects.filter(return_record__is_deleted=False).select_related("return_record")

        if tenant_id:
            purchases = purchases.filter(tenant_id=tenant_id)
            sale_items = sale_items.filter(sale__tenant_id=tenant_id)
            return_items = return_items.filter(return_record__tenant_id=tenant_id)

        for p in purchases:
            totals[(p.tenant_id, p.product_id, p.branch_id)] += p.qty

        for item in sale_items:
            totals[(item.sale.tenant_id, item.product_id, item.sale.branch_id)] -= item.qty

        for item in return_items:
            totals[(item.return_record.tenant_id, item.product_id, item.return_record.branch_id)] += item.qty

        unlimited_ids = set(Product.objects.filter(unlimited=True).values_list("id", flat=True))

        updated = 0
        with transaction.atomic():
            for (t_id, product_id, branch_id), qty in totals.items():
                if product_id in unlimited_ids:
                    continue
                ProductStock.objects.update_or_create(
                    tenant_id=t_id, product_id=product_id, branch_id=branch_id, defaults={"quantity": qty},
                )
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Reconciled {updated} product/branch stock rows."))
