from django.contrib import admin

from portfolio.models import Portfolio, Position, Transaction


class PositionInline(admin.TabularInline):
    model = Position
    extra = 0
    readonly_fields = ("quantity", "avg_price")


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "initial_cash", "cash", "created_at")
    search_fields = ("name", "user__email")
    readonly_fields = ("cash", "created_at")
    inlines = (PositionInline,)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cash = obj.initial_cash
        super().save_model(request, obj, form, change)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "portfolio",
        "share",
        "side",
        "quantity",
        "price",
        "realized_pnl",
        "executed_at",
    )
    list_filter = ("side",)
    search_fields = ("portfolio__name", "share__ticker", "portfolio__user__email")
    readonly_fields = ("realized_pnl",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
