from decimal import Decimal

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dashboard.models import Share
from market.services import latest_price
from portfolio.models import Portfolio, Position, Transaction
from portfolio.services import TradeError, execute_trade, portfolio_valuation


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = ("id", "name", "initial_cash", "cash", "created_at")
        read_only_fields = ("cash", "created_at")

    def validate_name(self, value):
        request = self.context["request"]
        queryset = Portfolio.objects.filter(user=request.user, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Портфель с таким названием уже существует")
        return value

    def update(self, instance, validated_data):
        validated_data.pop("initial_cash", None)
        return super().update(instance, validated_data)


class PositionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    name = serializers.CharField(source="share.name", read_only=True)

    class Meta:
        model = Position
        fields = ("id", "portfolio", "share", "ticker", "name", "quantity", "avg_price")
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="share.ticker", read_only=True)
    total = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    class Meta:
        model = Transaction
        fields = (
            "id",
            "portfolio",
            "share",
            "ticker",
            "side",
            "quantity",
            "price",
            "total",
            "realized_pnl",
            "note",
            "executed_at",
        )
        read_only_fields = fields


class TradeInputSerializer(serializers.Serializer):
    share = serializers.PrimaryKeyRelatedField(queryset=Share.objects.all())
    side = serializers.ChoiceField(choices=Transaction.Side.choices)
    quantity = serializers.DecimalField(
        max_digits=18, decimal_places=6, min_value=Decimal("0.000001")
    )
    price = serializers.DecimalField(
        max_digits=18,
        decimal_places=6,
        min_value=Decimal("0.000001"),
        required=False,
    )
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if "price" not in attrs:
            market_price = latest_price(attrs["share"])
            if market_price is None:
                raise serializers.ValidationError(
                    {"price": "Нет рыночной цены — укажите цену явно"}
                )
            attrs["price"] = market_price
        return attrs


class PortfolioViewSet(viewsets.ModelViewSet):
    serializer_class = PortfolioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user).prefetch_related(
            "positions__share"
        )

    def perform_create(self, serializer):
        initial_cash = serializer.validated_data["initial_cash"]
        serializer.save(user=self.request.user, cash=initial_cash)

    @action(detail=True, methods=["get", "post"], url_path="trades")
    def trades(self, request, pk=None):
        portfolio = self.get_object()
        if request.method == "GET":
            queryset = Transaction.objects.filter(portfolio=portfolio).select_related(
                "share"
            )
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = TransactionSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = TransactionSerializer(queryset, many=True)
            return Response(serializer.data)

        serializer = TradeInputSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            trade = execute_trade(
                portfolio=portfolio,
                share=serializer.validated_data["share"],
                side=serializer.validated_data["side"],
                quantity=serializer.validated_data["quantity"],
                price=serializer.validated_data["price"],
                note=serializer.validated_data.get("note", ""),
            )
        except TradeError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(TransactionSerializer(trade).data, status=201)

    @action(detail=True, methods=["get"])
    def valuation(self, request, pk=None):
        portfolio = self.get_object()
        data = portfolio_valuation(portfolio)
        return Response(
            {
                "portfolio": portfolio.id,
                "cash": data["cash"],
                "market_value": data["market_value"],
                "cost_basis": data["cost_basis"],
                "unrealized_pnl": data["unrealized_pnl"],
                "realized_pnl": data["realized_pnl"],
                "equity": data["equity"],
                "initial_cash": data["initial_cash"],
                "total_pnl": data["total_pnl"],
                "return_pct": data["return_pct"],
                "positions": [
                    {
                        "share": row["share"].id,
                        "ticker": row["share"].ticker,
                        "quantity": row["quantity"],
                        "avg_price": row["avg_price"],
                        "current_price": row["current_price"],
                        "market_value": row["market_value"],
                        "cost_basis": row["cost_basis"],
                        "unrealized_pnl": row["unrealized_pnl"],
                    }
                    for row in data["positions"]
                ],
            }
        )


class PositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Position.objects.filter(
            portfolio__user=self.request.user
        ).select_related("share")


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(
            portfolio__user=self.request.user
        ).select_related("share")
