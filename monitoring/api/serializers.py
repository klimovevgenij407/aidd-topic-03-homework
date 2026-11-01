from rest_framework import serializers

from monitoring.models import Notification, Watchlist, WatchlistItem


class WatchlistSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = Watchlist
        fields = ("id", "name", "items_count", "created_at")
        read_only_fields = ("id", "created_at", "items_count")


class WatchlistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WatchlistItem
        fields = (
            "id",
            "watchlist",
            "share",
            "target_price",
            "direction",
            "is_active",
            "condition_met",
            "last_notified_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "condition_met",
            "last_notified_at",
            "created_at",
        )

    def validate(self, attrs):
        watchlist = attrs.get("watchlist") or (
            self.instance.watchlist if self.instance else None
        )
        share = attrs.get("share") or (self.instance.share if self.instance else None)
        request = self.context.get("request")
        if watchlist and request and watchlist.user_id != request.user.id:
            raise serializers.ValidationError(
                {"watchlist": "Можно использовать только свои списки."}
            )
        if watchlist and share:
            duplicates = WatchlistItem.objects.filter(
                watchlist=watchlist,
                share=share,
            )
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {"share": "Эта акция уже добавлена в список."}
                )
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "watchlist_item",
            "share",
            "price",
            "message",
            "created_at",
            "is_read",
        )
        read_only_fields = (
            "id",
            "watchlist_item",
            "share",
            "price",
            "message",
            "created_at",
        )
