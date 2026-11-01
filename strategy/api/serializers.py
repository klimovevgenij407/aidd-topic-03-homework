from rest_framework import serializers

from strategy.models import Strategy, StrategyTrade


class StrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = (
            "id",
            "name",
            "share",
            "buy_below",
            "sell_above",
            "initial_cash",
            "quantity",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        buy_below = attrs.get("buy_below") or (
            self.instance.buy_below if self.instance else None
        )
        sell_above = attrs.get("sell_above") or (
            self.instance.sell_above if self.instance else None
        )
        if buy_below and sell_above and buy_below >= sell_above:
            raise serializers.ValidationError(
                {"sell_above": "Цена продажи должна быть выше цены покупки."}
            )
        return attrs


class StrategyTradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyTrade
        fields = (
            "id",
            "strategy",
            "side",
            "price",
            "quantity",
            "executed_at",
            "reason",
            "created_at",
        )
        read_only_fields = fields


class StrategyStateSerializer(serializers.Serializer):
    cash = serializers.DecimalField(max_digits=20, decimal_places=2)
    position = serializers.DecimalField(max_digits=20, decimal_places=6)
    last_price = serializers.DecimalField(
        max_digits=20,
        decimal_places=9,
        allow_null=True,
    )
    equity = serializers.DecimalField(max_digits=20, decimal_places=2)
    pnl = serializers.DecimalField(max_digits=20, decimal_places=2)
    return_percent = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        allow_null=True,
    )
    trades_count = serializers.IntegerField()
