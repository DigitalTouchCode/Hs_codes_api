from django.contrib import admin

from pos.models import (
    ActivityLog, Branch, Customer, Expense, PosProfile, Product, ProductStock,
    Purchase, Return, Sale, Tenant,
)

admin.site.register(Tenant)
admin.site.register(PosProfile)
admin.site.register(Branch)
admin.site.register(Product)
admin.site.register(ProductStock)
admin.site.register(Customer)
admin.site.register(Sale)
admin.site.register(Return)
admin.site.register(Purchase)
admin.site.register(Expense)
admin.site.register(ActivityLog)
