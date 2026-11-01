"""Market-data providers.

The application talks to a provider interface rather than directly to a broker
SDK. This keeps the web application runnable without a token or network access
and makes the external integration replaceable/testable.

The live provider uses the official T-Invest Python SDK
(``t-tech-investments`` / import ``t_tech.invest``), which replaced the removed
``tinkoff-investments`` package.
"""

from __future__ import annotations

import hashlib
import logging
import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from dashboard.models import Share

logger = logging.getLogger(__name__)

PRICE_QUANT = Decimal("0.000000001")


class MarketDataError(RuntimeError):
    """Raised when market data cannot be obtained or configured."""


@dataclass(frozen=True, slots=True)
class Quote:
    figi: str
    price: Decimal
    at: datetime
    source: str = "live"

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("Quote price must be positive")


@dataclass(frozen=True, slots=True)
class Candle:
    at: datetime
    close: Decimal


class MarketDataProvider(Protocol):
    def get_last_quotes(self, shares: Sequence[Share]) -> dict[str, Quote]:
        """Return the latest quote keyed by FIGI."""

    def get_daily_candles(self, share: Share, days: int = 180) -> list[Candle]:
        """Return daily candles ordered from oldest to newest."""


def _round_price(value: Decimal | float) -> Decimal:
    return Decimal(str(value)).quantize(PRICE_QUANT, rounding=ROUND_HALF_UP)


def _stable_seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def _aware(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


class SimulatedProvider:
    """Deterministic pseudo-market data for local development and tests.

    Prices are derived from a hash of the instrument's FIGI. The provider does
    not perform network calls, so the complete application can be demonstrated
    without a T-Invest token.
    """

    def _base_price(self, share: Share) -> Decimal:
        if share.last_price and share.last_price > 0:
            return Decimal(share.last_price)
        seed = _stable_seed(share.figi)
        rubles = Decimal(50 + seed % 950)
        kopecks = Decimal((seed // 17) % 100) / Decimal(100)
        return _round_price(rubles + kopecks)

    def get_last_quotes(self, shares: Sequence[Share]) -> dict[str, Quote]:
        now = timezone.now()
        quotes: dict[str, Quote] = {}
        for share in shares:
            base = self._base_price(share)
            # Stable within a minute, varies between ticks.
            rng = random.Random(f"{share.figi}:{now:%Y%m%d%H%M}")
            change = Decimal(str(rng.uniform(-0.025, 0.025)))
            price = max(Decimal("0.01"), _round_price(base * (Decimal("1") + change)))
            quotes[share.figi] = Quote(
                figi=share.figi,
                price=price,
                at=now,
                source="simulated",
            )
        return quotes

    def get_daily_candles(self, share: Share, days: int = 180) -> list[Candle]:
        days = max(1, int(days))
        end = timezone.localdate()
        start = end - timedelta(days=days - 1)
        base = self._base_price(share)
        rng = random.Random(f"{share.figi}:history:{days}")
        current = base * Decimal("0.85")
        current_tz = timezone.get_current_timezone()
        candles: list[Candle] = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            drift = Decimal(str(rng.uniform(-0.018, 0.018)))
            current = max(
                Decimal("0.01"), _round_price(current * (Decimal("1") + drift))
            )
            close = base if offset == days - 1 else current
            candles.append(
                Candle(
                    at=timezone.make_aware(datetime.combine(day, time.min), current_tz),
                    close=_round_price(close),
                )
            )
        return candles


class TinkoffProvider:
    """Live provider backed by the official T-Invest Python SDK."""

    def __init__(self, token: str | None = None) -> None:
        self.token = (token or settings.TINKOFF_TOKEN or "").strip()
        if not self.token:
            raise MarketDataError(
                "TINKOFF_TOKEN is empty; set it or use MARKET_DATA_PROVIDER=simulated"
            )

    @staticmethod
    def _sdk():
        try:
            from t_tech.invest import CandleInterval, Client
            from t_tech.invest.utils import now, quotation_to_decimal
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise MarketDataError(
                "t-tech-investments is not installed. "
                "Install requirements-marketdata.txt to enable live data."
            ) from exc
        return Client, CandleInterval, now, quotation_to_decimal

    def get_last_quotes(self, shares: Sequence[Share]) -> dict[str, Quote]:
        if not shares:
            return {}
        Client, _candle_interval, _now, quotation_to_decimal = self._sdk()
        try:
            with Client(self.token) as client:
                response = client.market_data.get_last_prices(
                    figi=[share.figi for share in shares],
                )
        except Exception as exc:  # SDK raises several gRPC exception types
            raise MarketDataError(f"T-Invest API error: {exc}") from exc

        by_figi = {item.figi: item for item in response.last_prices}
        quotes: dict[str, Quote] = {}
        for share in shares:
            item = by_figi.get(share.figi)
            if item is None:
                logger.warning("No last price returned for %s", share.figi)
                continue
            price = _round_price(quotation_to_decimal(item.price))
            quotes[share.figi] = Quote(
                figi=share.figi,
                price=price,
                at=_aware(item.time),
                source="live",
            )
        return quotes

    def get_daily_candles(self, share: Share, days: int = 180) -> list[Candle]:
        Client, CandleInterval, now, quotation_to_decimal = self._sdk()
        days = max(1, int(days))
        try:
            with Client(self.token) as client:
                raw_candles = client.get_all_candles(
                    figi=share.figi,
                    from_=now() - timedelta(days=days),
                    interval=CandleInterval.CANDLE_INTERVAL_DAY,
                )
                candles = [
                    Candle(
                        at=_aware(candle.time),
                        close=_round_price(quotation_to_decimal(candle.close)),
                    )
                    for candle in raw_candles
                ]
        except Exception as exc:
            raise MarketDataError(f"T-Invest API error: {exc}") from exc

        candles.sort(key=lambda candle: candle.at)
        return candles


def get_provider(mode: str | None = None) -> MarketDataProvider:
    """Build a provider according to the configured mode.

    ``auto`` uses the live provider when a token is configured and falls back to
    simulated data when it is not (or when the optional SDK is unavailable).
    """

    selected = (mode or settings.MARKET_DATA_PROVIDER or "auto").strip().lower()
    if selected == "simulated":
        return SimulatedProvider()
    if selected == "auto":
        if not settings.TINKOFF_TOKEN:
            return SimulatedProvider()
        try:
            return TinkoffProvider()
        except MarketDataError:
            logger.warning(
                "Live market data is unavailable; falling back to simulated data",
                exc_info=True,
            )
            return SimulatedProvider()
    if selected in {"tinkoff", "t-invest", "live"}:
        return TinkoffProvider()
    raise MarketDataError(f"Unknown MARKET_DATA_PROVIDER: {selected!r}")
