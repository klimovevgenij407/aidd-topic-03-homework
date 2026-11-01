from django.urls import path

from watchlist.views import (
    NotificationListView,
    NotificationReadView,
    PriceAlertCreateView,
    PriceAlertToggleView,
    WatchlistDeleteView,
    WatchlistDetailView,
    WatchlistIndexView,
    WatchlistItemDeleteView,
)

app_name = "watchlist"

urlpatterns = [
    path("watchlists/", WatchlistIndexView.as_view(), name="index"),
    path("watchlists/<int:pk>/", WatchlistDetailView.as_view(), name="detail"),
    path("watchlists/<int:pk>/delete/", WatchlistDeleteView.as_view(), name="delete"),
    path(
        "watchlists/items/<int:pk>/delete/",
        WatchlistItemDeleteView.as_view(),
        name="item-delete",
    ),
    path(
        "watchlists/items/<int:item_pk>/alerts/",
        PriceAlertCreateView.as_view(),
        name="alert-create",
    ),
    path(
        "watchlists/alerts/<int:pk>/toggle/",
        PriceAlertToggleView.as_view(),
        name="alert-toggle",
    ),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
]
