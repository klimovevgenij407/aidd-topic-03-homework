from rest_framework import serializers

from dashboard.models import PriceSnapshot, Share


class PriceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSnapshot
        fields = ("id", "price", "captured_at", "source")


class PriceStatsSerializer(serializers.Serializer):
    first = serializers.DecimalField(max_digits=20, decimal_places=9)
    last = serializers.DecimalField(max_digits=20, decimal_places=9)
    absolute_change = serializers.DecimalField(max_digits=20, decimal_places=9)
    percent_change = serializers.DecimalField(
        max_digits=20,
        decimal_places=9,
        allow_null=True,
    )
    minimum = serializers.DecimalField(max_digits=20, decimal_places=9)
    maximum = serializers.DecimalField(max_digits=20, decimal_places=9)
    average = serializers.DecimalField(max_digits=20, decimal_places=9)
    count = serializers.IntegerField()


class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = (
            "id",
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "uid",
            "last_price",
            "is_trend_high",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "uid",
            "last_price",
            "is_trend_high",
            "updated_at",
        )

    def validate_ticker(self, value: str) -> str:
        return value.strip().upper()

    def validate_figi(self, value: str) -> str:
        return value.strip()

    def validate_isin(self, value: str) -> str:
        return value.strip().upper()
