from django.urls import path

from strategy.views import (
    StrategyCreateView,
    StrategyDeleteView,
    StrategyDetailView,
    StrategyListView,
    StrategyToggleView,
    StrategyUpdateView,
)

app_name = "strategy"

urlpatterns = [
    path("strategies/", StrategyListView.as_view(), name="strategy_list"),
    path("strategies/create/", StrategyCreateView.as_view(), name="strategy_create"),
    path(
        "strategies/<int:pk>/",
        StrategyDetailView.as_view(),
        name="strategy_detail",
    ),
    path(
        "strategies/<int:pk>/edit/",
        StrategyUpdateView.as_view(),
        name="strategy_update",
    ),
    path(
        "strategies/<int:pk>/delete/",
        StrategyDeleteView.as_view(),
        name="strategy_delete",
    ),
    path(
        "strategies/<int:pk>/toggle/",
        StrategyToggleView.as_view(),
        name="strategy_toggle",
    ),
]
