from rest_framework import routers

from dashboard.api.v1.views import ShareViewSet
from portfolio.api import PortfolioViewSet, PositionViewSet, TransactionViewSet
from strategy.api import StrategyRuleViewSet, StrategyTradeViewSet, StrategyViewSet
from watchlist.api import (
    NotificationViewSet,
    PriceAlertViewSet,
    WatchlistItemViewSet,
    WatchlistViewSet,
)

router = routers.DefaultRouter()
router.register(r"shares", ShareViewSet)
router.register(r"watchlists", WatchlistViewSet, basename="watchlist")
router.register(r"watchlist-items", WatchlistItemViewSet, basename="watchlist-item")
router.register(r"price-alerts", PriceAlertViewSet, basename="price-alert")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"portfolios", PortfolioViewSet, basename="portfolio")
router.register(r"positions", PositionViewSet, basename="position")
router.register(r"transactions", TransactionViewSet, basename="transaction")
router.register(r"strategies", StrategyViewSet, basename="strategy")
router.register(r"strategy-rules", StrategyRuleViewSet, basename="strategy-rule")
router.register(r"strategy-trades", StrategyTradeViewSet, basename="strategy-trade")
