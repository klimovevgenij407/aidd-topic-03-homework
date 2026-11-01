"""Price history storage, statistics and chart rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from plotly.graph_objs import Scatter
from plotly.offline import plot

from dashboard.models import PriceSnapshot, Share
from dashboard.services.market_data import get_provider


@dataclass(frozen=True, slots=True)
class PriceStats:
    first: Decimal
    last: Decimal
    absolute_change: Decimal
    percent_change: Decimal | None
    minimum: Decimal
    maximum: Decimal
    average: Decimal
    count: int


def ensure_price_history(
    share: Share,
    days: int = 180,
    *,
    force: bool = False,
) -> list[PriceSnapshot]:
    """Ensure enough daily snapshots exist and return the selected period.

    The provider is contacted only when the stored history is insufficient. This
    keeps normal page views independent from the external API after the initial
    backfill.
    """

    days = max(1, int(days))
    start = timezone.now() - timedelta(days=days)
    existing = list(
        PriceSnapshot.objects.filter(
            share=share,
            captured_at__gte=start,
        ).order_by("captured_at", "id")
    )
    if not force and len(existing) >= max(2, days // 2):
        return existing

    candles = get_provider().get_daily_candles(share, days=days)
    if candles:
        PriceSnapshot.objects.bulk_create(
            [
                PriceSnapshot(
                    share=share,
                    price=candle.close,
                    captured_at=candle.at,
                    source=PriceSnapshot.Source.HISTORY,
                )
                for candle in candles
            ],
            ignore_conflicts=True,
        )

    return list(
        PriceSnapshot.objects.filter(
            share=share,
            captured_at__gte=start,
        ).order_by("captured_at", "id")
    )


def calculate_stats(snapshots: Sequence[PriceSnapshot]) -> PriceStats | None:
    if not snapshots:
        return None

    prices = [snapshot.price for snapshot in snapshots]
    first = prices[0]
    last = prices[-1]
    absolute_change = last - first
    percent_change = (absolute_change / first * Decimal("100")) if first != 0 else None
    return PriceStats(
        first=first,
        last=last,
        absolute_change=absolute_change,
        percent_change=percent_change,
        minimum=min(prices),
        maximum=max(prices),
        average=sum(prices) / len(prices),
        count=len(prices),
    )


def build_chart(share: Share, snapshots: Sequence[PriceSnapshot]) -> str:
    if not snapshots:
        return ""

    figure = Scatter(
        x=[snapshot.captured_at for snapshot in snapshots],
        y=[float(snapshot.price) for snapshot in snapshots],
        mode="lines",
        name=share.ticker,
        opacity=0.85,
        line={"color": "#0d6efd", "width": 2},
    )
    return plot(
        [figure],
        output_type="div",
        include_plotlyjs="cdn",
        show_link=False,
        link_text="",
        config={"displayModeBar": False, "responsive": True},
    )


def get_history(
    share: Share,
    days: int = 180,
) -> tuple[list[PriceSnapshot], PriceStats | None, str]:
    snapshots = ensure_price_history(share, days=days)
    return snapshots, calculate_stats(snapshots), build_chart(share, snapshots)


def get_graph(share: Share, days: int = 180) -> str:
    """Backward-compatible chart helper used by the detail view."""

    snapshots = ensure_price_history(share, days=days)
    return build_chart(share, snapshots)
