from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Watchlist(models.Model):
    """Персональный список наблюдения."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlists",
        verbose_name="Пользователь",
    )
    name = models.CharField(max_length=120, verbose_name="Название")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")

    class Meta:
        verbose_name = "Список наблюдения"
        verbose_name_plural = "Списки наблюдения"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_user_watchlist_name"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} / {self.name}"


class WatchlistItem(models.Model):
    """Акция в списке наблюдения."""

    watchlist = models.ForeignKey(
        Watchlist,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Список наблюдения",
    )
    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.CASCADE,
        related_name="watchlist_items",
        verbose_name="Акция",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Заметка")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Добавлена")

    class Meta:
        verbose_name = "Акция в списке наблюдения"
        verbose_name_plural = "Акции в списках наблюдения"
        ordering = ["share__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["watchlist", "share"], name="unique_watchlist_share"
            )
        ]

    def __str__(self) -> str:
        return f"{self.watchlist.name}: {self.share.ticker}"


class PriceAlert(models.Model):
    """Целевой ценовой уровень для акции из списка наблюдения."""

    class Condition(models.TextChoices):
        ABOVE = "above", "Цена выше или равна"
        BELOW = "below", "Цена ниже или равна"

    item = models.ForeignKey(
        WatchlistItem,
        on_delete=models.CASCADE,
        related_name="alerts",
        verbose_name="Акция в списке",
    )
    condition = models.CharField(
        max_length=10, choices=Condition.choices, verbose_name="Условие"
    )
    target_price = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Целевая цена"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    triggered_at = models.DateTimeField(
        blank=True, null=True, verbose_name="Сработал"
    )
    triggered_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name="Цена срабатывания",
    )

    class Meta:
        verbose_name = "Целевая цена"
        verbose_name_plural = "Целевые цены"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(target_price__gt=0),
                name="price_alert_target_positive",
            )
        ]

    def clean(self):
        if self.target_price is not None and self.target_price <= 0:
            raise ValidationError({"target_price": "Целевая цена должна быть больше нуля"})

    def condition_met(self, price) -> bool:
        if self.condition == self.Condition.ABOVE:
            return price >= self.target_price
        return price <= self.target_price

    def __str__(self) -> str:
        return f"{self.item.share.ticker} {self.get_condition_display()} {self.target_price}"


class Notification(models.Model):
    """Уведомление пользователя о срабатывании целевой цены."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Пользователь",
    )
    alert = models.ForeignKey(
        PriceAlert,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Целевая цена",
    )
    price_snapshot = models.ForeignKey(
        "market.PriceSnapshot",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="notifications",
        verbose_name="Снимок цены",
    )
    price = models.DecimalField(max_digits=18, decimal_places=6, verbose_name="Цена")
    message = models.CharField(max_length=255, verbose_name="Сообщение")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["alert", "price_snapshot"],
                name="unique_alert_snapshot_notification",
            )
        ]

    def __str__(self) -> str:
        return self.message
