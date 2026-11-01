from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("user/", include("user.urls")),
    path("", include("watchlist.urls")),
    path("", include("portfolio.urls")),
    path("", include("strategy.urls")),
    # Совместимость с URL исходной версии: /userlogin/, /userregistration/, /userlogout/
    path(
        "userlogin/",
        RedirectView.as_view(
            pattern_name="user:auth", permanent=True, query_string=True
        ),
    ),
    path(
        "userregistration/",
        RedirectView.as_view(
            pattern_name="user:registration", permanent=True, query_string=True
        ),
    ),
    path(
        "userlogout/",
        RedirectView.as_view(
            pattern_name="user:logout", permanent=True, query_string=True
        ),
    ),
]
