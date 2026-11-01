from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from dashboard.models import PriceSnapshot, Share


class Strategy(models.Model):
    """Виртуальная стратегия покупки/продажи по ценовым порогам."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Акция",
    )
    buy_below = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
        verbose_name="Покупать при цене не выше",
    )
    sell_above = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
        verbose_name="Продавать при цене не ниже",
    )
    initial_cash = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal("100000"),
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Начальный капитал",
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.000001"))],
        verbose_name="Размер сделки (пусто — весь капитал)",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="uniq_user_strategy_name",
            ),
            models.CheckConstraint(
                condition=models.Q(buy_below__gt=0),
                name="strategy_buy_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(sell_above__gt=0),
                name="strategy_sell_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(initial_cash__gt=0),
                name="strategy_cash_positive",
            ),
        ]
        verbose_name = "Стратегия"
        verbose_name_plural = "Стратегии"

    def __str__(self) -> str:
        return f"{self.name} ({self.share.ticker})"

    def get_absolute_url(self) -> str:
        return reverse("strategy:strategy_detail", args=[self.pk])

    def clean(self):
        super().clean()
        if self.buy_below and self.sell_above and self.buy_below >= self.sell_above:
            raise ValidationError(
                {"sell_above": "Цена продажи должна быть выше цены покупки."}
            )


class StrategyTrade(models.Model):
    """Виртуальная сделка, совершённая симулятором."""

    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.CASCADE,
        related_name="trades",
        verbose_name="Стратегия",
    )
    side = models.CharField(
        max_length=10,
        choices=Side.choices,
        verbose_name="Операция",
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        verbose_name="Цена",
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        verbose_name="Количество",
    )
    executed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Дата",
    )
    price_snapshot = models.ForeignKey(
        PriceSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="strategy_trades",
        verbose_name="Снимок цены",
    )
    reason = models.CharField(max_length=255, verbose_name="Причина")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        ordering = ["executed_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["strategy", "price_snapshot", "side"],
                name="uniq_strategy_snapshot_side",
            )
        ]
        verbose_name = "Сделка стратегии"
        verbose_name_plural = "Сделки стратегий"

    def __str__(self) -> str:
        return (
            f"{self.strategy.name}: {self.get_side_display()} "
            f"{self.quantity} @ {self.price}"
        )
