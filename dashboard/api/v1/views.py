from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.models import Share
from market.models import PriceSnapshot
from market.services import ensure_history, history_stats

from .serializer import ShareSerializer


class ShareFilter(filters.FilterSet):
    class Meta:
        model = Share
        fields = ("name", "ticker")


class ShareViewSet(viewsets.ModelViewSet):
    serializer_class = ShareSerializer
    queryset = Share.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = (OrderingFilter, filters.DjangoFilterBackend, SearchFilter)
    filterset_class = ShareFilter
    ordering_fields = ["name", "ticker"]
    search_fields = ["$name"]


class SharePriceHistoryView(APIView):
    """История сохранённых цен с абсолютным и процентным изменением."""

    permission_classes = [AllowAny]

    def get(self, request):
        share_id = request.query_params.get("share")
        if not share_id:
            return Response({"detail": "Параметр share обязателен"}, status=400)
        try:
            share_id = int(share_id)
        except (TypeError, ValueError):
            return Response({"detail": "share должен быть целым числом"}, status=400)
        share = get_object_or_404(Share, pk=share_id)

        try:
            days = int(request.query_params.get("days", 180))
        except (TypeError, ValueError):
            return Response({"detail": "days должен быть целым числом"}, status=400)
        if not 1 <= days <= 3650:
            return Response({"detail": "days должен быть в диапазоне 1..3650"}, status=400)

        ensure_history(share, days=days)
        start = timezone.localdate() - timedelta(days=days)
        snapshots = list(
            PriceSnapshot.objects.filter(
                share=share, captured_at__date__gte=start
            ).order_by("captured_at")
        )
        stats = history_stats(snapshots)

        return Response(
            {
                "share": {
                    "id": share.id,
                    "ticker": share.ticker,
                    "name": share.name,
                    "currency": share.currency,
                },
                "days": days,
                "points": [
                    {
                        "captured_at": snapshot.captured_at,
                        "price": snapshot.price,
                        "source": snapshot.source,
                    }
                    for snapshot in snapshots
                ],
                "stats": stats,
            }
        )
