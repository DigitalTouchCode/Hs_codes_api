from django.contrib import admin
from .models import Client, Testimonial


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "email", "created_at"]
    search_fields = ["first_name", "last_name", "phone"]


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["display_name", "rating", "is_published", "created_at"]
    list_editable = ["is_published"]
    list_filter = ["is_published", "rating"]
