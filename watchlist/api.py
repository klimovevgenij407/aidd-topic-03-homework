from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from watchlist.models import Notification, PriceAlert, Watchlist, WatchlistItem
from watchlist.services import rearm_alert


class PriceAlertSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = PriceAlert
        fields = (
            "id",
            "item",
            "condition",
            "target_price",
            "is_active",
            "created_at",
            "triggered_at",
            "triggered_price",
        )
        read_only_fields = ("created_at", "triggered_at", "triggered_price")

    def validate_item(self, value):
        request = self.context["request"]
        if value.watchlist.user_id != request.user.id:
            raise serializers.ValidationError("Чужой список наблюдения")
        return value

    def validate_target_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть больше нуля")
        return value


class WatchlistItemSerializer(serializers.ModelSerializer):
    alerts = PriceAlertSerializer(many=True, read_only=True)
    share_ticker = serializers.CharField(source="share.ticker", read_only=True)

    class Meta:
        model = WatchlistItem
        fields = ("id", "watchlist", "share", "share_ticker", "note", "added_at", "alerts")
        read_only_fields = ("added_at",)

    def validate_watchlist(self, value):
        request = self.context["request"]
        if value.user_id != request.user.id:
            raise serializers.ValidationError("Чужой список наблюдения")
        return value


class WatchlistSerializer(serializers.ModelSerializer):
    items = WatchlistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Watchlist
        fields = ("id", "name", "created_at", "items")
        read_only_fields = ("created_at",)

    def validate_name(self, value):
        request = self.context["request"]
        queryset = Watchlist.objects.filter(user=request.user, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Список с таким названием уже существует")
        return value


class NotificationSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="alert.item.share.ticker", read_only=True)
    condition = serializers.CharField(source="alert.condition", read_only=True)
    target_price = serializers.DecimalField(
        source="alert.target_price", max_digits=18, decimal_places=6, read_only=True
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "alert",
            "ticker",
            "condition",
            "target_price",
            "price",
            "message",
            "created_at",
            "is_read",
        )
        read_only_fields = fields


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user).prefetch_related(
            "items__share", "items__alerts"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WatchlistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WatchlistItem.objects.filter(
            watchlist__user=self.request.user
        ).select_related("share")


class PriceAlertViewSet(viewsets.ModelViewSet):
    serializer_class = PriceAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PriceAlert.objects.filter(
            item__watchlist__user=self.request.user
        ).select_related("item__share")

    @action(detail=True, methods=["post"])
    def rearm(self, request, pk=None):
        alert = self.get_object()
        rearm_alert(alert)
        return Response(self.get_serializer(alert).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related(
            "alert__item__share"
        )

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)
