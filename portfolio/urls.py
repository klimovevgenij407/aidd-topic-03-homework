from django.urls import path

from portfolio.views import (
    PortfolioDeleteView,
    PortfolioDetailView,
    PortfolioListView,
)

app_name = "portfolio"

urlpatterns = [
    path("portfolios/", PortfolioListView.as_view(), name="index"),
    path("portfolios/<int:pk>/", PortfolioDetailView.as_view(), name="detail"),
    path("portfolios/<int:pk>/delete/", PortfolioDeleteView.as_view(), name="delete"),
]
