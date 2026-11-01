from django.db import models


class PriceSnapshot(models.Model):
    """Сохранённая рыночная цена акции на момент времени."""

    share = models.ForeignKey(
        "dashboard.Share",
        on_delete=models.CASCADE,
        related_name="price_snapshots",
        verbose_name="Акция",
    )
    price = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Цена"
    )
    captured_at = models.DateTimeField(db_index=True, verbose_name="Момент цены")
    source = models.CharField(max_length=20, default="synthetic", verbose_name="Источник")

    class Meta:
        verbose_name = "Снимок цены"
        verbose_name_plural = "История цен"
        ordering = ["-captured_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["share", "captured_at"],
                name="unique_share_snapshot_moment",
            )
        ]
        indexes = [
            models.Index(
                fields=["share", "-captured_at"],
                name="idx_snapshot_share_time",
            )
        ]

    def __str__(self) -> str:
        return f"{self.share.ticker} {self.price} @ {self.captured_at:%Y-%m-%d %H:%M}"
