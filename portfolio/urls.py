from django.urls import path

from portfolio.views import (
    PortfolioCreateView,
    PortfolioDeleteView,
    PortfolioDetailView,
    PortfolioListView,
    PortfolioTransactionCreateView,
    PortfolioTransactionDeleteView,
    PortfolioTransactionUpdateView,
    PortfolioUpdateView,
)

app_name = "portfolio"

urlpatterns = [
    path("portfolios/", PortfolioListView.as_view(), name="portfolio_list"),
    path("portfolios/create/", PortfolioCreateView.as_view(), name="portfolio_create"),
    path(
        "portfolios/<int:pk>/",
        PortfolioDetailView.as_view(),
        name="portfolio_detail",
    ),
    path(
        "portfolios/<int:pk>/edit/",
        PortfolioUpdateView.as_view(),
        name="portfolio_update",
    ),
    path(
        "portfolios/<int:pk>/delete/",
        PortfolioDeleteView.as_view(),
        name="portfolio_delete",
    ),
    path(
        "portfolios/<int:portfolio_pk>/transactions/add/",
        PortfolioTransactionCreateView.as_view(),
        name="transaction_create",
    ),
    path(
        "portfolios/transactions/<int:pk>/edit/",
        PortfolioTransactionUpdateView.as_view(),
        name="transaction_update",
    ),
    path(
        "portfolios/transactions/<int:pk>/delete/",
        PortfolioTransactionDeleteView.as_view(),
        name="transaction_delete",
    ),
]
