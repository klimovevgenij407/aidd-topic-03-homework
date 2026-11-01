from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from dashboard.models import Share
from dashboard.services.market_data import MarketDataError
from dashboard.services.price_history import get_history

from .serializer import (
    PriceSnapshotSerializer,
    PriceStatsSerializer,
    ShareSerializer,
)


class ShareFilter(filters.FilterSet):
    class Meta:
        model = Share
        fields = ("name", "ticker")


class ShareViewSet(viewsets.ModelViewSet):
    serializer_class = ShareSerializer
    queryset = Share.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filter_backends = (OrderingFilter, filters.DjangoFilterBackend, SearchFilter)
    filterset_class = ShareFilter
    ordering_fields = ["name", "ticker"]
    search_fields = ["name", "ticker"]

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        share = self.get_object()
        try:
            days = int(request.query_params.get("days", 180))
        except (TypeError, ValueError):
            days = 180
        if days not in {7, 30, 90, 180, 365}:
            days = 180
        try:
            snapshots, stats, _plot = get_history(share, days=days)
        except MarketDataError as exc:
            return Response(
                {"detail": f"Market data unavailable: {exc}"},
                status=503,
            )
        return Response(
            {
                "share": share.pk,
                "days": days,
                "stats": PriceStatsSerializer(stats).data if stats else None,
                "points": PriceSnapshotSerializer(snapshots, many=True).data,
            }
        )
