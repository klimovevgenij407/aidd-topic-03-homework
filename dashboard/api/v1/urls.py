from django.urls import include, path

from dashboard.api.v1.views import SharePriceHistoryView
from dashboard.api.v1.router import router

urlpatterns = [
    path("price-history/", SharePriceHistoryView.as_view(), name="price-history"),
    path("", include(router.urls)),
]
