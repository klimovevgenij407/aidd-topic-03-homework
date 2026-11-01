from django.contrib import admin

from strategy.models import Strategy, StrategyRule, StrategyTrade


class StrategyRuleInline(admin.TabularInline):
    model = StrategyRule
    extra = 0


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "share",
        "initial_cash",
        "cash",
        "quantity",
        "is_active",
    )
    list_filter = ("is_active", "share")
    search_fields = ("name", "user__email", "share__ticker")
    readonly_fields = ("cash", "quantity", "avg_price", "realized_pnl")
    inlines = (StrategyRuleInline,)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cash = obj.initial_cash
        super().save_model(request, obj, form, change)


@admin.register(StrategyTrade)
class StrategyTradeAdmin(admin.ModelAdmin):
    list_display = (
        "strategy",
        "side",
        "quantity",
        "price",
        "realized_pnl",
        "executed_at",
    )
    list_filter = ("side",)
    search_fields = ("strategy__name", "strategy__user__email")
    readonly_fields = (
        "strategy",
        "rule",
        "price_snapshot",
        "side",
        "quantity",
        "price",
        "realized_pnl",
        "cash_after",
        "position_after",
        "executed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
