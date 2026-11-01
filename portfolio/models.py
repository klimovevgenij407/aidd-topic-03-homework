from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Share


class Portfolio(models.Model):
    """Виртуальный инвестиционный портфель."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolios",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    base_currency = models.CharField(
        max_length=10,
        default="rub",
        verbose_name="Базовая валюта",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="uniq_user_portfolio_name",
            )
        ]
        verbose_name = "Портфель"
        verbose_name_plural = "Портфели"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("portfolio:portfolio_detail", args=[self.pk])


class PortfolioTransaction(models.Model):
    """Виртуальная операция покупки или продажи."""

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
        Share,
        on_delete=models.CASCADE,
        related_name="portfolio_transactions",
        verbose_name="Акция",
    )
    side = models.CharField(
        max_length=10,
        choices=Side.choices,
        verbose_name="Операция",
    )
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0.000001"))],
        verbose_name="Количество",
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
        verbose_name="Цена",
    )
    commission = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Комиссия",
    )
    executed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Дата операции",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        ordering = ["executed_at", "id"]
        indexes = [
            models.Index(
                fields=["portfolio", "share", "executed_at"],
                name="portfolio_share_time_idx",
            )
        ]
        verbose_name = "Операция портфеля"
        verbose_name_plural = "Операции портфеля"

    def __str__(self) -> str:
        return (
            f"{self.get_side_display()} {self.quantity} {self.share.ticker} "
            f"@ {self.price}"
        )
