from django.utils import timezone
from rest_framework import serializers

from portfolio.models import Portfolio, PortfolioTransaction
from portfolio.services import validate_transaction


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = ("id", "name", "base_currency", "created_at")
        read_only_fields = ("id", "created_at")


class PortfolioTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioTransaction
        fields = (
            "id",
            "portfolio",
            "share",
            "side",
            "quantity",
            "price",
            "commission",
            "executed_at",
            "note",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        portfolio = attrs.get("portfolio") or (
            self.instance.portfolio if self.instance else None
        )
        share = attrs.get("share") or (self.instance.share if self.instance else None)
        side = attrs.get("side") or (self.instance.side if self.instance else None)
        quantity = attrs.get("quantity") or (
            self.instance.quantity if self.instance else None
        )
        executed_at = attrs.get("executed_at") or (
            self.instance.executed_at if self.instance else None
        )
        request = self.context.get("request")
        if portfolio and request and portfolio.user_id != request.user.id:
            raise serializers.ValidationError(
                {"portfolio": "Можно использовать только свои портфели."}
            )
        if portfolio and share and side and quantity:
            try:
                validate_transaction(
                    portfolio,
                    share,
                    side,
                    quantity,
                    executed_at or timezone.now(),
                    exclude_pk=self.instance.pk if self.instance else None,
                )
            except Exception as exc:
                raise serializers.ValidationError({"detail": str(exc)}) from exc
        return attrs


class PositionSerializer(serializers.Serializer):
    share = serializers.IntegerField(source="share.pk")
    ticker = serializers.CharField(source="share.ticker")
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    average_price = serializers.DecimalField(max_digits=20, decimal_places=9)
    last_price = serializers.DecimalField(
        max_digits=20,
        decimal_places=9,
        allow_null=True,
    )
    market_value = serializers.DecimalField(max_digits=20, decimal_places=9)
    realized_pnl = serializers.DecimalField(max_digits=20, decimal_places=9)
    unrealized_pnl = serializers.DecimalField(max_digits=20, decimal_places=9)
    total_pnl = serializers.DecimalField(max_digits=20, decimal_places=9)


class PortfolioSummarySerializer(serializers.Serializer):
    total_cost_basis = serializers.DecimalField(max_digits=20, decimal_places=9)
    total_market_value = serializers.DecimalField(max_digits=20, decimal_places=9)
    total_realized_pnl = serializers.DecimalField(max_digits=20, decimal_places=9)
    total_unrealized_pnl = serializers.DecimalField(max_digits=20, decimal_places=9)
    total_pnl = serializers.DecimalField(max_digits=20, decimal_places=9)
    positions = PositionSerializer(many=True)
