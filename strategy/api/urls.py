from django.urls import include, path
from rest_framework import routers

from strategy.api.views import StrategyTradeViewSet, StrategyViewSet

router = routers.DefaultRouter()
router.register("strategies", StrategyViewSet, basename="api-strategy")
router.register(
    "strategy-trades",
    StrategyTradeViewSet,
    basename="api-strategy-trade",
)

urlpatterns = [
    path("", include(router.urls)),
]
