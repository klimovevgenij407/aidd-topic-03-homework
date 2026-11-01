from django.contrib import admin

from dashboard.models import Share


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = (
        "figi",
        "isin",
        "name",
        "ticker",
        "currency",
        "last_price",
        "is_trend_high",
        "updated_at",
    )
    search_fields = ("figi", "isin", "name", "ticker")
    readonly_fields = ("last_price", "is_trend_high", "updated_at")
    fields = (
        "figi",
        "isin",
        "name",
        "ticker",
        "currency",
        "uid",
        "last_price",
        "is_trend_high",
        "updated_at",
    )
