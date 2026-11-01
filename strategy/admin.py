from django.contrib import admin

from strategy.models import Strategy, StrategyTrade


class StrategyTradeInline(admin.TabularInline):
    model = StrategyTrade
    extra = 0
    readonly_fields = ("side", "price", "quantity", "executed_at", "reason")


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "share",
        "buy_below",
        "sell_above",
        "is_active",
    )
    list_filter = ("is_active", "share")
    search_fields = ("name", "user__email", "share__ticker")
    inlines = (StrategyTradeInline,)


@admin.register(StrategyTrade)
class StrategyTradeAdmin(admin.ModelAdmin):
    list_display = ("strategy", "side", "price", "quantity", "executed_at")
    list_filter = ("side",)
    search_fields = (
        "strategy__name",
        "strategy__user__email",
        "strategy__share__ticker",
    )
    readonly_fields = ("executed_at", "created_at")
