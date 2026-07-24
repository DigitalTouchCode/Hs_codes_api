from django.contrib import admin
from .models import Repair, RepairImage, RepairStatusLog, RepairNote, RepairCost


class RepairImageInline(admin.TabularInline):
    model = RepairImage
    extra = 0
    readonly_fields = ["uploaded_at"]


class RepairStatusLogInline(admin.TabularInline):
    model = RepairStatusLog
    extra = 0
    readonly_fields = ["previous_status", "new_status", "changed_by", "sms_sent", "created_at"]


class RepairNoteInline(admin.TabularInline):
    model = RepairNote
    extra = 0
    readonly_fields = ["added_by", "created_at"]


class RepairCostInline(admin.TabularInline):
    model = RepairCost
    extra = 0
    readonly_fields = ["added_by", "created_at"]


@admin.register(Repair)
class RepairAdmin(admin.ModelAdmin):
    list_display = ["ref", "client", "device_brand", "device_type", "status", "total_cost", "created_at"]
    list_filter = ["status", "device_type", "assigned_to"]
    search_fields = ["ref", "client__first_name", "client__last_name", "client__phone"]
    readonly_fields = ["ref", "created_at", "updated_at", "total_cost"]
    inlines = [RepairImageInline, RepairCostInline, RepairNoteInline, RepairStatusLogInline]
    fieldsets = (
        ("Booking", {"fields": ("ref", "client", "status", "assigned_to", "estimated_completion", "collected_at")}),
        ("Device", {"fields": ("device_type", "device_brand", "device_model", "serial_number")}),
        ("Problem", {"fields": ("problem_description",)}),
        ("Meta", {"fields": ("created_at", "updated_at", "total_cost")}),
    )
