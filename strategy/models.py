from django.conf import settings
from django.db import models
from django.utils import timezone


class Strategy(models.Model):
    """Виртуальная стратегия покупки/продажи по заданным условиям."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=120, verbose_name="Название")
    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.CASCADE,
        related_name="strategies",
        verbose_name="Акция",
    )
    initial_cash = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Начальный капитал"
    )
    cash = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Свободные средства"
    )
    quantity = models.DecimalField(
        max_digits=18, decimal_places=6, default=0, verbose_name="Количество акций"
    )
    avg_price = models.DecimalField(
        max_digits=18, decimal_places=6, default=0, verbose_name="Средняя цена"
    )
    realized_pnl = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name="Реализованная прибыль"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        verbose_name = "Стратегия"
        verbose_name_plural = "Стратегии"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_user_strategy_name"
            ),
            models.CheckConstraint(
                condition=models.Q(initial_cash__gte=0),
                name="strategy_initial_cash_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(cash__gte=0), name="strategy_cash_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="strategy_quantity_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.share.ticker})"


class StrategyRule(models.Model):
    """Правило стратегии: при выполнении условия совершить операцию."""

    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    class Condition(models.TextChoices):
        ABOVE = "above", "Цена выше или равна"
        BELOW = "below", "Цена ниже или равна"

    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.CASCADE,
        related_name="rules",
        verbose_name="Стратегия",
    )
    side = models.CharField(max_length=4, choices=Side.choices, verbose_name="Операция")
    condition = models.CharField(
        max_length=10, choices=Condition.choices, verbose_name="Условие"
    )
    threshold = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Порог цены"
    )
    quantity = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Количество"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Правило стратегии"
        verbose_name_plural = "Правила стратегии"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(threshold__gt=0),
                name="strategy_rule_threshold_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="strategy_rule_quantity_positive",
            ),
        ]

    def condition_met(self, price) -> bool:
        if self.condition == self.Condition.ABOVE:
            return price >= self.threshold
        return price <= self.threshold

    def __str__(self) -> str:
        return f"{self.get_side_display()} при {self.get_condition_display()} {self.threshold}"


class StrategyTrade(models.Model):
    """Журнал виртуальных сделок, совершённых стратегией."""

    strategy = models.ForeignKey(
        Strategy,
        on_delete=models.CASCADE,
        related_name="trades",
        verbose_name="Стратегия",
    )
    rule = models.ForeignKey(
        StrategyRule,
        on_delete=models.PROTECT,
        related_name="trades",
        verbose_name="Правило",
    )
    price_snapshot = models.ForeignKey(
        "market.PriceSnapshot",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="strategy_trades",
        verbose_name="Снимок цены",
    )
    side = models.CharField(max_length=4, choices=StrategyRule.Side.choices, verbose_name="Операция")
    quantity = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Количество"
    )
    price = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Цена")
    realized_pnl = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="Реализованная прибыль",
    )
    cash_after = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Средства после"
    )
    position_after = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Позиция после"
    )
    executed_at = models.DateTimeField(
        default=timezone.now, verbose_name="Время сделки"
    )

    class Meta:
        verbose_name = "Сделка стратегии"
        verbose_name_plural = "Сделки стратегии"
        ordering = ["-executed_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["strategy", "rule", "price_snapshot"],
                name="unique_strategy_rule_snapshot_trade",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_side_display()} {self.quantity} по {self.price}"
