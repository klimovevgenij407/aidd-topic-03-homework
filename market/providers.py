"""Провайдеры рыночных данных.

Приложение не зависит напрямую от T-Bank Invest API: работа с ним скрыта за
интерфейсом ``MarketDataProvider``. Это позволяет запускать и тестировать
систему без токена и без установленного SDK (детерминированный синтетический
провайдер), а в production использовать официальный invest-python.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Iterable, Protocol

from django.conf import settings
from django.utils import timezone


class MarketDataError(RuntimeError):
    """Рыночные данные недоступны."""


@dataclass(frozen=True)
class Quote:
    figi: str
    price: Decimal
    currency: str
    as_of: datetime


@dataclass(frozen=True)
class Candle:
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0


@dataclass(frozen=True)
class InstrumentInfo:
    figi: str
    isin: str
    name: str
    ticker: str
    currency: str
    uid: str


class MarketDataProvider(Protocol):
    name: str

    def get_quote(self, share) -> Quote: ...

    def get_candles(self, share, start: date, end: date) -> list[Candle]: ...

    def list_instruments(self) -> Iterable[InstrumentInfo]: ...


def _aware_utc(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _quotation_to_decimal(quotation) -> Decimal:
    """Quotation из SDK хранит цену как units + nano (1e-9)."""
    return (Decimal(quotation.units) + Decimal(quotation.nano) / Decimal(1_000_000_000)).quantize(
        Decimal("0.000001")
    )


class TinkoffProvider:
    """Официальный SDK T-Bank Invest API (пакет ``tinkoff-investments``)."""

    name = "tbank"

    def __init__(self, token: str):
        if not token:
            raise MarketDataError("TINKOFF_INVEST_TOKEN не задан")
        if importlib.util.find_spec("tinkoff") is None:
            raise MarketDataError(
                "SDK invest-python не установлен: pip install -r requirements-market.txt"
            )
        self.token = token

    def _client(self):
        from tinkoff.invest import Client

        return Client(self.token)

    def get_quote(self, share) -> Quote:
        with self._client() as client:
            response = client.market_data.get_last_prices(figi=[share.figi])
            if not response.last_prices:
                raise MarketDataError(f"Нет цены для {share.ticker}")
            last_price = response.last_prices[0]
            return Quote(
                figi=share.figi,
                price=_quotation_to_decimal(last_price.price),
                currency=share.currency,
                as_of=_aware_utc(last_price.time),
            )

    def get_candles(self, share, start: date, end: date) -> list[Candle]:
        from tinkoff.invest import CandleInterval

        start_dt = datetime.combine(start, time.min, tzinfo=dt_timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=dt_timezone.utc)
        with self._client() as client:
            candles = client.get_all_candles(
                figi=share.figi,
                from_=start_dt,
                to=end_dt,
                interval=CandleInterval.CANDLE_INTERVAL_DAY,
            )
            return [
                Candle(
                    time=_aware_utc(candle.time),
                    open=_quotation_to_decimal(candle.open),
                    high=_quotation_to_decimal(candle.high),
                    low=_quotation_to_decimal(candle.low),
                    close=_quotation_to_decimal(candle.close),
                    volume=int(candle.volume),
                )
                for candle in candles
            ]

    def list_instruments(self) -> Iterable[InstrumentInfo]:
        with self._client() as client:
            response = client.instruments.shares()
            return [
                InstrumentInfo(
                    figi=item.figi,
                    isin=item.isin,
                    name=item.name,
                    ticker=item.ticker,
                    currency=item.currency,
                    uid=item.uid,
                )
                for item in response.instruments
            ]


_SYNTHETIC_CATALOG = (
    ("SYNTH00001", "RU0000000001", "Сбербанк", "SBER", "rub"),
    ("SYNTH00002", "RU0000000002", "Газпром", "GAZP", "rub"),
    ("SYNTH00003", "RU0000000003", "Лукойл", "LKOH", "rub"),
    ("SYNTH00004", "RU0000000004", "Яндекс", "YDEX", "rub"),
    ("SYNTH00005", "US0000000005", "Apple", "AAPL", "usd"),
)


def _fraction(*parts: str) -> float:
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


class SyntheticProvider:
    """Детерминированный демонстрационный провайдер.

    Цена зависит только от тикера и даты/времени, поэтому история и текущие
    котировки воспроизводимы между запусками и в тестах.
    """

    name = "synthetic"
    epoch = date(2020, 1, 1)

    def _phase(self, ticker: str) -> float:
        return _fraction("phase", ticker) * 2 * math.pi

    def _base_price(self, ticker: str) -> float:
        return 80 + _fraction("base", ticker) * 420

    def _daily_close(self, ticker: str, day: date) -> Decimal:
        index = (day - self.epoch).days
        phase = self._phase(ticker)
        long_wave = 0.18 * math.sin(2 * math.pi * index / 420 + phase)
        short_wave = 0.06 * math.sin(2 * math.pi * index / 37 + phase * 0.7)
        noise = (_fraction("day", ticker, day.isoformat()) - 0.5) * 0.02
        price = self._base_price(ticker) * (1 + long_wave + short_wave + noise)
        return Decimal(str(max(price, 1.0))).quantize(Decimal("0.000001"))

    def _intraday_price(self, ticker: str, moment: datetime) -> Decimal:
        close = self._daily_close(ticker, moment.date())
        minutes = moment.hour * 60 + moment.minute
        phase = self._phase(ticker)
        move = 0.004 * math.sin(2 * math.pi * minutes / 1440 + phase * 1.3)
        return (close * Decimal(str(1 + move))).quantize(Decimal("0.000001"))

    def get_quote(self, share) -> Quote:
        now = timezone.now().astimezone(dt_timezone.utc).replace(second=0, microsecond=0)
        return Quote(
            figi=share.figi,
            price=self._intraday_price(share.ticker, now),
            currency=share.currency,
            as_of=now,
        )

    def get_candles(self, share, start: date, end: date) -> list[Candle]:
        candles: list[Candle] = []
        day = start
        while day <= end:
            close = self._daily_close(share.ticker, day)
            spread = close * Decimal("0.006")
            open_price = (close - spread * Decimal(
                str(_fraction("open", share.ticker, day.isoformat()) - 0.5)
            )).quantize(Decimal("0.000001"))
            high = max(open_price, close) + spread
            low = min(open_price, close) - spread
            volume = 100_000 + int(_fraction("volume", share.ticker, day.isoformat()) * 900_000)
            candles.append(
                Candle(
                    time=datetime.combine(day, time.min, tzinfo=dt_timezone.utc),
                    open=open_price,
                    high=high.quantize(Decimal("0.000001")),
                    low=max(low, Decimal("0.000001")).quantize(Decimal("0.000001")),
                    close=close,
                    volume=volume,
                )
            )
            day += timedelta(days=1)
        return candles

    def list_instruments(self) -> Iterable[InstrumentInfo]:
        return [
            InstrumentInfo(
                figi=figi,
                isin=isin,
                name=name,
                ticker=ticker,
                currency=currency,
                uid=f"uid-{ticker.lower()}-0000-0000-0000-000000000000",
            )
            for figi, isin, name, ticker, currency in _SYNTHETIC_CATALOG
        ]


def get_provider() -> MarketDataProvider:
    """Выбирает провайдера по настройке MARKET_DATA_PROVIDER.

    ``auto`` использует T-Bank, если задан токен и установлен SDK, иначе
    синтетические данные. Явный ``tbank`` без токена/SDK приводит к ошибке,
    чтобы проблема конфигурации не маскировалась.
    """

    configured = (getattr(settings, "MARKET_DATA_PROVIDER", "auto") or "auto").lower()
    token = getattr(settings, "TINKOFF_TOKEN", "")

    if configured == "synthetic":
        return SyntheticProvider()
    if configured == "tbank":
        return TinkoffProvider(token)
    if token and importlib.util.find_spec("tinkoff") is not None:
        return TinkoffProvider(token)
    return SyntheticProvider()
