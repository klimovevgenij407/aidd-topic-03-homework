import uuid

from django.db import models
from django.utils import timezone


class Share(models.Model):
    """Акция (инструмент фондового рынка)."""

    figi = models.CharField(max_length=255, unique=True, verbose_name="FIGI")
    isin = models.CharField(max_length=255, verbose_name="ISIN")
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=20, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        verbose_name="UID инструмента",
    )
    last_price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        blank=True,
        null=True,
        verbose_name="Текущая цена",
    )
    is_trend_high = models.BooleanField(
        blank=True,
        null=True,
        verbose_name="Цена растёт",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        blank=True,
        null=True,
        verbose_name="Обновлено",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Акция"
        verbose_name_plural = "Акции"

    def __str__(self) -> str:
        return f"{self.ticker} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.uid:
            self.uid = str(uuid.uuid4())
        return super().save(*args, **kwargs)


class PriceSnapshot(models.Model):
    """Сохранённое значение цены акции на момент времени."""

    class Source(models.TextChoices):
        LIVE = "live", "Онлайн"
        HISTORY = "history", "История"
        SIMULATED = "simulated", "Симуляция"

    share = models.ForeignKey(
        Share,
        on_delete=models.CASCADE,
        related_name="price_snapshots",
        verbose_name="Акция",
    )
    price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        verbose_name="Цена",
    )
    captured_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name="Время снимка",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.LIVE,
        verbose_name="Источник",
    )

    class Meta:
        ordering = ["-captured_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["share", "captured_at"],
                name="uniq_share_snapshot_time",
            )
        ]
        indexes = [
            models.Index(
                fields=["share", "-captured_at"],
                name="share_snapshot_time_idx",
            )
        ]
        verbose_name = "Снимок цены"
        verbose_name_plural = "История цен"

    def __str__(self) -> str:
        return f"{self.share.ticker} {self.price} @ {self.captured_at:%d.%m.%Y %H:%M}"
