"""Service for updating share prices and recording price snapshots."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from dashboard.models import PriceSnapshot, Share
from dashboard.services.market_data import get_provider

logger = logging.getLogger(__name__)


def update_share_prices(shares: list[Share] | None = None) -> int:
    """Fetch and persist the latest price for every share.

    A snapshot is stored for each successful quote. After a new snapshot is
    committed, watchlists and strategy simulators are evaluated. Errors for an
    individual share are logged and do not stop the remaining updates.
    """

    if shares is None:
        shares = list(Share.objects.all())
    else:
        shares = list(shares)

    if not shares:
        return 0

    quotes = get_provider().get_last_quotes(shares)
    updated = 0

    for share in shares:
        quote = quotes.get(share.figi)
        if quote is None:
            logger.warning("No quote for share %s (%s)", share.pk, share.figi)
            continue
        try:
            with transaction.atomic():
                locked = Share.objects.select_for_update().get(pk=share.pk)
                previous_price = locked.last_price
                locked.last_price = quote.price
                locked.is_trend_high = (
                    None if previous_price is None else quote.price > previous_price
                )
                locked.save(update_fields=["last_price", "is_trend_high", "updated_at"])
                snapshot, created = PriceSnapshot.objects.get_or_create(
                    share=locked,
                    captured_at=quote.at,
                    defaults={
                        "price": quote.price,
                        "source": quote.source,
                    },
                )
            if created:
                process_price_snapshot(snapshot)
            updated += 1
            logger.info(
                "Updated share %s: %s -> %s",
                share.pk,
                previous_price,
                quote.price,
            )
        except Exception:
            logger.exception("Failed to update share %s", share.pk)

    return updated


def process_price_snapshot(snapshot: PriceSnapshot) -> None:
    """Run feature handlers for a newly stored price snapshot.

    Imports are local to avoid a circular dependency between the market-data
    service and the feature apps. A failure in one feature must not roll back the
    price update or prevent other features from being evaluated.
    """

    from monitoring.services import evaluate_watchlists
    from strategy.services import evaluate_strategies

    for handler in (evaluate_watchlists, evaluate_strategies):
        try:
            handler(snapshot)
        except Exception:
            logger.exception(
                "Post-snapshot handler %s failed for snapshot %s",
                handler.__name__,
                snapshot.pk,
            )


def tick_price_snapshot(share: Share) -> PriceSnapshot | None:
    """Create a manual snapshot from the current share price (demo/testing)."""

    if share.last_price is None:
        return None
    snapshot, _created = PriceSnapshot.objects.get_or_create(
        share=share,
        captured_at=timezone.now(),
        defaults={
            "price": share.last_price,
            "source": PriceSnapshot.Source.SIMULATED,
        },
    )
    process_price_snapshot(snapshot)
    return snapshot
