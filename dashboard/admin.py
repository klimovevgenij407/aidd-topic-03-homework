from django.contrib import admin

from dashboard.models import PriceSnapshot, Share


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "name",
        "figi",
        "isin",
        "currency",
        "last_price",
        "is_trend_high",
        "updated_at",
    )
    list_filter = ("currency", "is_trend_high")
    search_fields = ("figi", "isin", "name", "ticker", "uid")
    readonly_fields = ("updated_at",)
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


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("share", "price", "captured_at", "source")
    list_filter = ("source", "share")
    search_fields = ("share__ticker", "share__name")
    date_hierarchy = "captured_at"
    readonly_fields = ("captured_at",)
