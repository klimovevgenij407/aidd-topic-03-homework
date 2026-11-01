from django.contrib import admin

from portfolio.models import Portfolio, PortfolioTransaction


class PortfolioTransactionInline(admin.TabularInline):
    model = PortfolioTransaction
    extra = 0


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "base_currency", "created_at")
    search_fields = ("name", "user__email")
    inlines = (PortfolioTransactionInline,)


@admin.register(PortfolioTransaction)
class PortfolioTransactionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "share", "side", "quantity", "price", "executed_at")
    list_filter = ("side", "share")
    search_fields = ("portfolio__name", "share__ticker", "portfolio__user__email")
