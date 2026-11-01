from django.contrib import admin

from monitoring.models import Notification, Watchlist, WatchlistItem


class WatchlistItemInline(admin.TabularInline):
    model = WatchlistItem
    extra = 0


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__email")
    inlines = (WatchlistItemInline,)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "created_at", "is_read")
    list_filter = ("is_read",)
    search_fields = ("message", "user__email", "share__ticker")
    readonly_fields = ("created_at",)
