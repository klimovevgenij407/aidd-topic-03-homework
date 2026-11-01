from django.urls import include, path
from rest_framework import routers

from portfolio.api.views import PortfolioTransactionViewSet, PortfolioViewSet

router = routers.DefaultRouter()
router.register("portfolios", PortfolioViewSet, basename="api-portfolio")
router.register(
    "portfolio-transactions",
    PortfolioTransactionViewSet,
    basename="api-portfolio-transaction",
)

urlpatterns = [
    path("", include(router.urls)),
]
