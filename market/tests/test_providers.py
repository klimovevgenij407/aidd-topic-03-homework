from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from market.providers import (
    MarketDataError,
    SyntheticProvider,
    TinkoffProvider,
    _quotation_to_decimal,
    get_provider,
)


class QuotationPrecisionTests(SimpleTestCase):
    def test_nano_part_is_not_lost(self):
        quotation = SimpleNamespace(units=100, nano=500_000_000)
        self.assertEqual(_quotation_to_decimal(quotation), Decimal("100.500000"))

    def test_small_nano_part(self):
        quotation = SimpleNamespace(units=0, nano=1)
        self.assertEqual(_quotation_to_decimal(quotation), Decimal("0.000000"))


class SyntheticProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = SyntheticProvider()

    def test_daily_close_is_deterministic(self):
        first = self.provider._daily_close("SBER", date(2026, 5, 1))
        second = self.provider._daily_close("SBER", date(2026, 5, 1))
        self.assertEqual(first, second)
        self.assertGreater(first, 0)

    def test_quote_is_stable_within_minute(self):
        fixed_now = datetime(2026, 5, 1, 10, 30, 45, tzinfo=dt_timezone.utc)
        share = SimpleNamespace(ticker="SBER", figi="FIGI", currency="rub")
        with patch("market.providers.timezone.now", return_value=fixed_now):
            first = self.provider.get_quote(share)
            second = self.provider.get_quote(share)
        self.assertEqual(first.price, second.price)
        self.assertEqual(first.as_of, datetime(2026, 5, 1, 10, 30, tzinfo=dt_timezone.utc))
        self.assertEqual(first.as_of.second, 0)
        self.assertEqual(first.as_of.microsecond, 0)

    def test_candles_are_ordered_and_consistent(self):
        share = SimpleNamespace(ticker="GAZP", figi="FIGI", currency="rub")
        candles = self.provider.get_candles(share, date(2026, 4, 1), date(2026, 4, 10))
        self.assertEqual(len(candles), 10)
        self.assertEqual([c.time.day for c in candles], list(range(1, 11)))
        for candle in candles:
            self.assertGreaterEqual(candle.high, candle.close)
            self.assertLessEqual(candle.low, candle.close)
            self.assertGreater(candle.close, 0)

    def test_instruments_are_unique(self):
        instruments = list(self.provider.list_instruments())
        self.assertGreaterEqual(len(instruments), 5)
        self.assertEqual(len({item.ticker for item in instruments}), len(instruments))
        self.assertEqual(len({item.figi for item in instruments}), len(instruments))


class ProviderSelectionTests(SimpleTestCase):
    @override_settings(MARKET_DATA_PROVIDER="auto", TINKOFF_TOKEN="")
    def test_auto_without_token_uses_synthetic(self):
        self.assertIsInstance(get_provider(), SyntheticProvider)

    @override_settings(MARKET_DATA_PROVIDER="synthetic", TINKOFF_TOKEN="secret")
    def test_explicit_synthetic(self):
        self.assertIsInstance(get_provider(), SyntheticProvider)

    @override_settings(MARKET_DATA_PROVIDER="tbank", TINKOFF_TOKEN="")
    def test_explicit_tbank_without_token_fails(self):
        with self.assertRaises(MarketDataError):
            get_provider()

    def test_tbank_provider_rejects_empty_token(self):
        with self.assertRaises(MarketDataError):
            TinkoffProvider("")
