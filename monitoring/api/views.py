from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from monitoring.api.serializers import (
    NotificationSerializer,
    WatchlistItemSerializer,
    WatchlistSerializer,
)
from monitoring.models import Notification, Watchlist, WatchlistItem


class WatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Watchlist.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WatchlistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WatchlistItemSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return WatchlistItem.objects.filter(
            watchlist__user=self.request.user
        ).select_related("watchlist", "share")

    def perform_create(self, serializer):
        watchlist = serializer.validated_data.get("watchlist")
        if watchlist and watchlist.user_id != self.request.user.id:
            raise PermissionDenied("Можно использовать только свои списки.")
        serializer.save()


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related(
            "share", "watchlist_item"
        )

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)
