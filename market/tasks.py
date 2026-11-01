from celery import shared_task
from django.conf import settings

from config.settings import logger
from market.services import ensure_history, refresh_all


@shared_task
def refresh_market_data() -> dict:
    """Периодическая задача: котировки -> снимки -> алерты -> стратегии."""

    summary = refresh_all()
    logger.info("Обновление рыночных данных: %s", summary)
    return summary


@shared_task
def backfill_history(days: int | None = None) -> dict:
    from dashboard.models import Share

    days = days or getattr(settings, "MARKET_DATA_HISTORY_DAYS", 180)
    total = 0
    for share in Share.objects.all():
        total += ensure_history(share, days=days)
    return {"snapshots": total, "days": days}
