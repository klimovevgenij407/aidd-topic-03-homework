from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("monitoring.api.urls")),
    path("api/v1/", include("portfolio.api.urls")),
    path("api/v1/", include("strategy.api.urls")),
    path("", include("monitoring.urls")),
    path("", include("portfolio.urls")),
    path("", include("strategy.urls")),
    path("", include("dashboard.urls")),
    path("user/", include("user.urls")),
]
