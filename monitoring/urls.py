from django.urls import path

from monitoring.views import (
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
    WatchlistCreateView,
    WatchlistDeleteView,
    WatchlistDetailView,
    WatchlistItemCreateView,
    WatchlistItemDeleteView,
    WatchlistItemUpdateView,
    WatchlistListView,
    WatchlistUpdateView,
)

app_name = "monitoring"

urlpatterns = [
    path("watchlists/", WatchlistListView.as_view(), name="watchlist_list"),
    path("watchlists/create/", WatchlistCreateView.as_view(), name="watchlist_create"),
    path(
        "watchlists/<int:pk>/",
        WatchlistDetailView.as_view(),
        name="watchlist_detail",
    ),
    path(
        "watchlists/<int:pk>/edit/",
        WatchlistUpdateView.as_view(),
        name="watchlist_update",
    ),
    path(
        "watchlists/<int:pk>/delete/",
        WatchlistDeleteView.as_view(),
        name="watchlist_delete",
    ),
    path(
        "watchlists/<int:watchlist_pk>/items/add/",
        WatchlistItemCreateView.as_view(),
        name="watchlist_item_create",
    ),
    path(
        "watchlists/items/<int:pk>/edit/",
        WatchlistItemUpdateView.as_view(),
        name="watchlist_item_update",
    ),
    path(
        "watchlists/items/<int:pk>/delete/",
        WatchlistItemDeleteView.as_view(),
        name="watchlist_item_delete",
    ),
    path("notifications/", NotificationListView.as_view(), name="notification_list"),
    path(
        "notifications/<int:pk>/read/",
        NotificationReadView.as_view(),
        name="notification_read",
    ),
    path(
        "notifications/read-all/",
        NotificationReadAllView.as_view(),
        name="notification_read_all",
    ),
]
