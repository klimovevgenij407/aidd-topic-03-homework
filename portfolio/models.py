from django.conf import settings
from django.db import models
from django.utils import timezone


class Portfolio(models.Model):
    """Виртуальный инвестиционный портфель."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=120, verbose_name="Название")
    initial_cash = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Начальный капитал"
    )
    cash = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Свободные средства"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Портфель"
        verbose_name_plural = "Портфели"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_user_portfolio_name"
            ),
            models.CheckConstraint(
                condition=models.Q(initial_cash__gte=0),
                name="portfolio_initial_cash_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(cash__gte=0), name="portfolio_cash_non_negative"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} / {self.name}"


class Position(models.Model):
    """Текущая позиция портфеля по акции (средневзвешенная цена)."""

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="Акция",
    )
    quantity = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Количество"
    )
    avg_price = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Средняя цена"
    )

    class Meta:
        verbose_name = "Позиция"
        verbose_name_plural = "Позиции"
        ordering = ["share__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "share"], name="unique_portfolio_share"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="position_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(avg_price__gte=0), name="position_avg_price_non_negative"
            ),
        ]

    @property
    def cost_basis(self):
        return self.quantity * self.avg_price

    def __str__(self) -> str:
        return f"{self.portfolio.name}: {self.share.ticker} × {self.quantity}"


class Transaction(models.Model):
    """История виртуальных операций покупки/продажи."""

    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Портфель",
    )
    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Акция",
    )
    side = models.CharField(max_length=4, choices=Side.choices, verbose_name="Операция")
    quantity = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Количество"
    )
    price = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Цена"
    )
    realized_pnl = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="Реализованная прибыль",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Комментарий")
    executed_at = models.DateTimeField(
        default=timezone.now, verbose_name="Время операции"
    )

    class Meta:
        verbose_name = "Операция"
        verbose_name_plural = "Операции"
        ordering = ["-executed_at", "-id"]
        indexes = [
            models.Index(
                fields=["portfolio", "-executed_at"],
                name="idx_transaction_portfolio_time",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="transaction_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="transaction_price_positive"
            ),
        ]

    @property
    def total(self):
        return self.quantity * self.price

    def __str__(self) -> str:
        return f"{self.get_side_display()} {self.share.ticker} × {self.quantity}"
