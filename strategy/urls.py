from django.urls import path

from strategy.views import (
    StrategyDeleteView,
    StrategyDetailView,
    StrategyListView,
    StrategyRuleDeleteView,
    StrategyRuleToggleView,
    StrategyRunView,
    StrategyToggleView,
)

app_name = "strategy"

urlpatterns = [
    path("strategies/", StrategyListView.as_view(), name="index"),
    path("strategies/<int:pk>/", StrategyDetailView.as_view(), name="detail"),
    path("strategies/<int:pk>/delete/", StrategyDeleteView.as_view(), name="delete"),
    path("strategies/<int:pk>/toggle/", StrategyToggleView.as_view(), name="toggle"),
    path("strategies/<int:pk>/run/", StrategyRunView.as_view(), name="run"),
    path(
        "strategies/rules/<int:pk>/toggle/",
        StrategyRuleToggleView.as_view(),
        name="rule-toggle",
    ),
    path(
        "strategies/rules/<int:pk>/delete/",
        StrategyRuleDeleteView.as_view(),
        name="rule-delete",
    ),
]
