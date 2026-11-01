from django.urls import include, path
from rest_framework import routers

from monitoring.api.views import (
    NotificationViewSet,
    WatchlistItemViewSet,
    WatchlistViewSet,
)

router = routers.DefaultRouter()
router.register("watchlists", WatchlistViewSet, basename="api-watchlist")
router.register("watchlist-items", WatchlistItemViewSet, basename="api-watchlist-item")
router.register("notifications", NotificationViewSet, basename="api-notification")

urlpatterns = [
    path("", include(router.urls)),
]
