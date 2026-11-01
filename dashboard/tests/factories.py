from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.utils import timezone

from dashboard.models import Share
from market.models import PriceSnapshot
from market.providers import Candle, Quote


def make_share(ticker: str = "AAPL", price=None, **overrides) -> Share:
    data = {
        "figi": f"FIGI-{ticker}",
        "isin": f"ISIN-{ticker}",
        "name": f"{ticker} Company",
        "ticker": ticker[:10],
        "currency": "usd",
        "uid": f"uid-{ticker}",
    }
    data.update(overrides)
    if price is not None:
        data["last_price"] = Decimal(str(price))
    return Share.objects.create(**data)


def make_snapshot(share: Share, price, captured_at=None, source="test") -> PriceSnapshot:
    return PriceSnapshot.objects.create(
        share=share,
        price=Decimal(str(price)),
        captured_at=captured_at or timezone.now(),
        source=source,
    )


def make_quote(share: Share, price, as_of=None) -> Quote:
    return Quote(
        figi=share.figi,
        price=Decimal(str(price)),
        currency=share.currency,
        as_of=as_of or timezone.now().replace(second=0, microsecond=0),
    )


def make_candle(day: str, close, share: Share | None = None) -> Candle:
    moment = datetime.fromisoformat(day).replace(tzinfo=dt_timezone.utc)
    value = Decimal(str(close))
    return Candle(
        time=moment,
        open=value,
        high=value + Decimal("1"),
        low=value - Decimal("1"),
        close=value,
        volume=1000,
    )


class StubProvider:
    name = "stub"

    def __init__(self, quote=None, candles=None):
        self._quote = quote
        self._candles = candles or []

    def get_quote(self, share: Share) -> Quote:
        return self._quote

    def get_candles(self, share, start, end):
        return self._candles

    def list_instruments(self):
        return []
