from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from portfolio.api.serializers import (
    PortfolioSerializer,
    PortfolioSummarySerializer,
    PortfolioTransactionSerializer,
)
from portfolio.models import Portfolio, PortfolioTransaction
from portfolio.services import calculate_portfolio


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        portfolio = self.get_object()
        summary = calculate_portfolio(portfolio)
        return Response(PortfolioSummarySerializer(summary).data)


class PortfolioTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioTransactionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return PortfolioTransaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related("portfolio", "share")

    def perform_create(self, serializer):
        portfolio = serializer.validated_data.get("portfolio")
        if portfolio and portfolio.user_id != self.request.user.id:
            raise PermissionDenied("Можно использовать только свои портфели.")
        serializer.save()
