from django.urls import include, path
from django.views.generic import RedirectView

from dashboard.views import (
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("shares/<int:pk>/", ShareDetailView.as_view(), name="detail"),
    path("shares/create/", ShareCreateView.as_view(), name="create"),
    path("shares/<int:pk>/update/", ShareUpdateView.as_view(), name="update"),
    path("shares/<int:pk>/delete/", ShareDeleteView.as_view(), name="delete"),
    path("api/", include("dashboard.api.urls")),
    # Совместимость с URL исходной версии.
    path(
        "<int:pk>",
        RedirectView.as_view(
            pattern_name="dashboard:detail", permanent=True, query_string=True
        ),
    ),
    path(
        "create",
        RedirectView.as_view(
            pattern_name="dashboard:create", permanent=True, query_string=True
        ),
    ),
    path(
        "update/<int:pk>",
        RedirectView.as_view(
            pattern_name="dashboard:update", permanent=True, query_string=True
        ),
    ),
    path(
        "delete/<int:pk>",
        RedirectView.as_view(
            pattern_name="dashboard:delete", permanent=True, query_string=True
        ),
    ),
]
