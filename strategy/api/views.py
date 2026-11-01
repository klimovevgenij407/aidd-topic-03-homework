from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from strategy.api.serializers import (
    StrategySerializer,
    StrategyStateSerializer,
    StrategyTradeSerializer,
)
from strategy.models import Strategy, StrategyTrade
from strategy.services import calculate_state, toggle_strategy


class StrategyViewSet(viewsets.ModelViewSet):
    serializer_class = StrategySerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Strategy.objects.filter(user=self.request.user).select_related("share")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        strategy = self.get_object()
        toggle_strategy(strategy)
        return Response(self.get_serializer(strategy).data)

    @action(detail=True, methods=["get"])
    def state(self, request, pk=None):
        strategy = self.get_object()
        state = calculate_state(strategy)
        return Response(StrategyStateSerializer(state).data)


class StrategyTradeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StrategyTradeSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return StrategyTrade.objects.filter(
            strategy__user=self.request.user
        ).select_related("strategy", "strategy__share")
