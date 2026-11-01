from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from dashboard.models import Share
from market.models import PriceSnapshot
from market.providers import Candle, Quote, get_provider
from config.settings import logger


@dataclass(frozen=True)
class RefreshResult:
    share: Share
    snapshot: PriceSnapshot
    price: Decimal
    is_trend_high: bool
    is_new_snapshot: bool = False


def record_quote(share: Share, quote: Quote, source: str | None = None) -> PriceSnapshot:
    snapshot, _ = PriceSnapshot.objects.get_or_create(
        share=share,
        captured_at=quote.as_of,
        defaults={"price": quote.price, "source": source or "unknown"},
    )
    return snapshot


def update_share_price(share: Share, quote: Quote) -> bool:
    previous = share.last_price
    is_trend_high = True if previous is None else quote.price >= previous
    share.last_price = quote.price
    share.is_trend_high = is_trend_high
    share.updated_at = timezone.now()
    share.save(update_fields=["last_price", "is_trend_high", "updated_at"])
    return is_trend_high


def refresh_share(share: Share, provider=None) -> RefreshResult:
    provider = provider or get_provider()
    quote = provider.get_quote(share)
    is_trend_high = update_share_price(share, quote)
    is_new_snapshot = not PriceSnapshot.objects.filter(
        share=share, captured_at=quote.as_of
    ).exists()
    snapshot = record_quote(share, quote, source=provider.name)
    logger.info(
        "Обновлена цена %s: %s %s", share.ticker, quote.price, quote.currency
    )
    return RefreshResult(
        share=share,
        snapshot=snapshot,
        price=quote.price,
        is_trend_high=is_trend_high,
        is_new_snapshot=is_new_snapshot,
    )


def refresh_all(provider=None) -> dict:
    """Обновляет цены всех акций и запускает алерты/стратегии.

    Ошибка по одной акции не прерывает обработку остальных.
    """

    provider = provider or get_provider()
    summary = {"updated": 0, "errors": 0, "snapshots": 0}

    # Импорт внутри функции, чтобы избежать циклических зависимостей приложений.
    from strategy.services import process_share_strategies
    from watchlist.services import process_share_alerts

    for share in Share.objects.all().iterator():
        try:
            result = refresh_share(share, provider=provider)
            summary["updated"] += 1
            summary["snapshots"] += int(result.is_new_snapshot)
            process_share_alerts(share, result.snapshot)
            process_share_strategies(share, result.snapshot)
        except Exception as exc:  # noqa: BLE001 - задача не должна падать целиком
            summary["errors"] += 1
            logger.error("Не удалось обновить %s: %s", share.ticker, exc)
    return summary


def ensure_history(share: Share, days: int | None = None, provider=None) -> int:
    """Догружает дневную историю из провайдера в PriceSnapshot.

    Возвращает количество фактически добавленных снимков.
    """

    days = days or getattr(settings, "MARKET_DATA_HISTORY_DAYS", 180)
    today = timezone.localdate()
    start_day = today - timedelta(days=days)
    provider = provider or get_provider()

    latest = (
        PriceSnapshot.objects.filter(share=share)
        .order_by("-captured_at")
        .values_list("captured_at", flat=True)
        .first()
    )
    earliest = (
        PriceSnapshot.objects.filter(share=share)
        .order_by("captured_at")
        .values_list("captured_at", flat=True)
        .first()
    )
    # Допускаем пропуски в начале периода (выходные/праздники), но не больше
    # 10% периода и не больше недели.
    tolerance = timedelta(days=min(7, max(1, days // 10)))
    covered_from = start_day + tolerance
    if (
        latest
        and latest.date() >= today
        and earliest
        and earliest.date() <= covered_from
    ):
        return 0

    try:
        candles: list[Candle] = provider.get_candles(share, start_day, today)
    except Exception as exc:  # noqa: BLE001 - история не должна ломать страницу
        logger.error("Не удалось загрузить историю %s: %s", share.ticker, exc)
        return 0

    existing = set(
        PriceSnapshot.objects.filter(
            share=share, captured_at__date__gte=start_day
        ).values_list("captured_at", flat=True)
    )
    objects = [
        PriceSnapshot(
            share=share,
            price=candle.close,
            captured_at=candle.time,
            source=provider.name,
        )
        for candle in candles
        if candle.time not in existing
    ]
    if not objects:
        return 0
    before = PriceSnapshot.objects.filter(
        share=share, captured_at__date__gte=start_day
    ).count()
    with transaction.atomic():
        PriceSnapshot.objects.bulk_create(objects, ignore_conflicts=True)
    added = (
        PriceSnapshot.objects.filter(
            share=share, captured_at__date__gte=start_day
        ).count()
        - before
    )
    logger.info("Загружено %s новых снимков для %s", added, share.ticker)
    return added


def latest_price(share: Share) -> Decimal | None:
    if share.last_price is not None:
        return share.last_price
    snapshot = (
        PriceSnapshot.objects.filter(share=share).order_by("-captured_at").first()
    )
    return snapshot.price if snapshot else None


def history_stats(snapshots) -> dict:
    points = list(snapshots)
    if not points:
        return {
            "count": 0,
            "first": None,
            "last": None,
            "change": None,
            "change_pct": None,
            "min": None,
            "max": None,
        }
    first = points[0].price
    last = points[-1].price
    change = last - first
    change_pct = (change / first * 100) if first else None
    return {
        "count": len(points),
        "first": first,
        "last": last,
        "change": change,
        "change_pct": change_pct,
        "min": min(point.price for point in points),
        "max": max(point.price for point in points),
    }
