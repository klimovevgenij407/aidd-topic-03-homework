from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from dashboard.models import PriceSnapshot, Share


class Watchlist(models.Model):
    """Персональный список наблюдения."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlists",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=100, verbose_name="Название")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="uniq_user_watchlist_name",
            )
        ]
        verbose_name = "Список наблюдения"
        verbose_name_plural = "Списки наблюдения"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("monitoring:watchlist_detail", args=[self.pk])


class WatchlistItem(models.Model):
    """Акция в списке наблюдения с целевым ценовым уровнем."""

    class Direction(models.TextChoices):
        ABOVE = "above", "Цена выше или равна"
        BELOW = "below", "Цена ниже или равна"

    watchlist = models.ForeignKey(
        Watchlist,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Список",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
        verbose_name="Акция",
    )
    target_price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
        verbose_name="Целевая цена",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        default=Direction.ABOVE,
        verbose_name="Направление условия",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    condition_met = models.BooleanField(
        default=False,
        verbose_name="Условие выполнено",
    )
    last_notified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последнее уведомление",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        ordering = ["share__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["watchlist", "share"],
                name="uniq_watchlist_share",
            )
        ]
        verbose_name = "Элемент списка наблюдения"
        verbose_name_plural = "Элементы списков наблюдения"

    def __str__(self) -> str:
        return f"{self.watchlist.name}: {self.share.ticker} {self.direction} {self.target_price}"

    def condition_matches(self, price: Decimal) -> bool:
        if self.direction == self.Direction.ABOVE:
            return price >= self.target_price
        return price <= self.target_price


class Notification(models.Model):
    """Уведомление о достижении целевого уровня."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Пользователь",
    )
    watchlist_item = models.ForeignKey(
        WatchlistItem,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Элемент списка",
    )
    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Акция",
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        verbose_name="Цена срабатывания",
    )
    price_snapshot = models.ForeignKey(
        PriceSnapshot,
        on_delete=models.CASCADE,
        related_name="watchlist_notifications",
        verbose_name="Снимок цены",
    )
    message = models.CharField(max_length=255, verbose_name="Сообщение")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["watchlist_item", "price_snapshot"],
                name="uniq_watchlist_notification_snapshot",
            )
        ]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self) -> str:
        return self.message
