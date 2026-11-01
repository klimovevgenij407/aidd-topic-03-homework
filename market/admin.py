from django.contrib import admin

from market.models import PriceSnapshot


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("share", "price", "captured_at", "source")
    list_filter = ("source",)
    search_fields = ("share__ticker", "share__name")
    date_hierarchy = "captured_at"
    readonly_fields = ("share", "price", "captured_at", "source")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
