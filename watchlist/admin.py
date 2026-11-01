from django.contrib import admin

from watchlist.models import Notification, PriceAlert, Watchlist, WatchlistItem


class WatchlistItemInline(admin.TabularInline):
    model = WatchlistItem
    extra = 0


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__email")
    inlines = (WatchlistItemInline,)


class PriceAlertInline(admin.TabularInline):
    model = PriceAlert
    extra = 0


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("watchlist", "share", "added_at")
    search_fields = ("watchlist__name", "share__ticker")
    inlines = (PriceAlertInline,)


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "condition",
        "target_price",
        "is_active",
        "triggered_at",
    )
    list_filter = ("condition", "is_active")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "price", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__email", "message")
