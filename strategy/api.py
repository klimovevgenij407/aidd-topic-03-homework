from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.settings import logger
from strategy.models import Strategy, StrategyRule, StrategyTrade
from strategy.services import run_strategy_now, strategy_metrics


class StrategyRuleSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = StrategyRule
        fields = (
            "id",
            "strategy",
            "side",
            "condition",
            "threshold",
            "quantity",
            "is_active",
            "created_at",
        )
        read_only_fields = ("created_at",)

    def validate_strategy(self, value):
        request = self.context["request"]
        if value.user_id != request.user.id:
            raise serializers.ValidationError("Чужая стратегия")
        return value


class StrategyTradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyTrade
        fields = (
            "id",
            "strategy",
            "rule",
            "side",
            "quantity",
            "price",
            "realized_pnl",
            "cash_after",
            "position_after",
            "executed_at",
        )
        read_only_fields = fields


class StrategySerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    rules = StrategyRuleSerializer(many=True, read_only=True)

    class Meta:
        model = Strategy
        fields = (
            "id",
            "name",
            "share",
            "ticker",
            "initial_cash",
            "cash",
            "quantity",
            "avg_price",
            "realized_pnl",
            "is_active",
            "created_at",
            "rules",
        )
        read_only_fields = (
            "cash",
            "quantity",
            "avg_price",
            "realized_pnl",
            "created_at",
        )

    def validate_name(self, value):
        request = self.context["request"]
        queryset = Strategy.objects.filter(user=request.user, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Стратегия с таким названием уже существует")
        return value

    def update(self, instance, validated_data):
        validated_data.pop("initial_cash", None)
        return super().update(instance, validated_data)


class StrategyViewSet(viewsets.ModelViewSet):
    serializer_class = StrategySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Strategy.objects.filter(user=self.request.user).select_related(
            "share"
        ).prefetch_related("rules")

    def perform_create(self, serializer):
        initial_cash = serializer.validated_data["initial_cash"]
        serializer.save(user=self.request.user, cash=initial_cash)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        strategy = self.get_object()
        try:
            trades = run_strategy_now(strategy)
        except Exception as exc:  # noqa: BLE001 - ошибка провайдера -> 503
            logger.error("Не удалось проверить стратегию %s: %s", strategy.pk, exc)
            return Response(
                {"detail": "Рыночные данные недоступны, попробуйте позже"},
                status=503,
            )
        return Response(
            {
                "executed": len(trades),
                "trades": StrategyTradeSerializer(trades, many=True).data,
            },
            status=201 if trades else 200,
        )

    @action(detail=True, methods=["get"], url_path="trades")
    def trades(self, request, pk=None):
        strategy = self.get_object()
        queryset = StrategyTrade.objects.filter(strategy=strategy)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                StrategyTradeSerializer(page, many=True).data
            )
        return Response(StrategyTradeSerializer(queryset, many=True).data)

    @action(detail=True, methods=["get"])
    def metrics(self, request, pk=None):
        strategy = self.get_object()
        data = strategy_metrics(strategy)
        data.pop("positions", None)
        return Response(data)


class StrategyRuleViewSet(viewsets.ModelViewSet):
    serializer_class = StrategyRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StrategyRule.objects.filter(
            strategy__user=self.request.user
        ).select_related("strategy__share")


class StrategyTradeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StrategyTradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return StrategyTrade.objects.filter(
            strategy__user=self.request.user
        ).select_related("strategy__share")
