from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from dashboard.tests.factories import (
    StubProvider,
    make_candle,
    make_quote,
    make_share,
    make_snapshot,
)
from market.models import PriceSnapshot
from market.services import (
    ensure_history,
    history_stats,
    latest_price,
    record_quote,
    refresh_all,
    refresh_share,
)


class RefreshShareTests(TestCase):
    def setUp(self):
        self.share = make_share("TEST", price=100)
        self.as_of = timezone.now().replace(second=0, microsecond=0)

    def test_refresh_updates_price_trend_and_snapshot(self):
        provider = StubProvider(make_quote(self.share, "150.25", self.as_of))
        result = refresh_share(self.share, provider=provider)

        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal("150.250000"))
        self.assertTrue(self.share.is_trend_high)
        self.assertTrue(result.is_trend_high)
        self.assertIsNotNone(self.share.updated_at)
        snapshot = PriceSnapshot.objects.get(share=self.share)
        self.assertEqual(snapshot.price, Decimal("150.250000"))
        self.assertEqual(snapshot.captured_at, self.as_of)
        self.assertEqual(snapshot.source, "stub")

    def test_price_drop_sets_trend_false(self):
        provider = StubProvider(make_quote(self.share, "80", self.as_of))
        result = refresh_share(self.share, provider=provider)
        self.assertFalse(result.is_trend_high)
        self.share.refresh_from_db()
        self.assertFalse(self.share.is_trend_high)

    def test_first_price_is_treated_as_growth(self):
        share = make_share("NEW", price=None)
        provider = StubProvider(make_quote(share, "10", self.as_of))
        self.assertTrue(refresh_share(share, provider=provider).is_trend_high)

    def test_same_snapshot_is_not_duplicated(self):
        quote = make_quote(self.share, "120", self.as_of)
        record_quote(self.share, quote, source="stub")
        record_quote(self.share, quote, source="stub")
        self.assertEqual(PriceSnapshot.objects.filter(share=self.share).count(), 1)

    def test_second_refresh_in_same_minute_is_not_marked_as_new(self):
        provider = StubProvider(make_quote(self.share, "120", self.as_of))
        first = refresh_share(self.share, provider=provider)
        second = refresh_share(self.share, provider=provider)
        self.assertTrue(first.is_new_snapshot)
        self.assertFalse(second.is_new_snapshot)


class HistoryTests(TestCase):
    def setUp(self):
        self.share = make_share("HIST")

    def test_stats_absolute_and_percentage_change(self):
        points = [
            make_snapshot(self.share, 100, timezone.now() - timedelta(days=2)),
            make_snapshot(self.share, 110, timezone.now() - timedelta(days=1)),
            make_snapshot(self.share, 90, timezone.now()),
        ]
        stats = history_stats(points)
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["first"], Decimal("100"))
        self.assertEqual(stats["last"], Decimal("90"))
        self.assertEqual(stats["change"], Decimal("-10"))
        self.assertEqual(stats["change_pct"], Decimal("-10"))
        self.assertEqual(stats["min"], Decimal("90"))
        self.assertEqual(stats["max"], Decimal("110"))

    def test_empty_stats(self):
        stats = history_stats([])
        self.assertEqual(stats["count"], 0)
        self.assertIsNone(stats["change_pct"])

    def test_ensure_history_is_idempotent(self):
        today = timezone.localdate()
        candles = [
            make_candle((today - timedelta(days=2)).isoformat(), 10),
            make_candle((today - timedelta(days=1)).isoformat(), 11),
            make_candle(today.isoformat(), 12),
        ]
        provider = StubProvider(candles=candles)
        added = ensure_history(self.share, days=5, provider=provider)
        self.assertEqual(added, 3)
        self.assertEqual(ensure_history(self.share, days=5, provider=provider), 0)
        self.assertEqual(PriceSnapshot.objects.filter(share=self.share).count(), 3)

    def test_ensure_history_backfills_when_only_recent_quote_exists(self):
        today = timezone.localdate()
        make_snapshot(self.share, "50", timezone.now())
        candles = [
            make_candle((today - timedelta(days=2)).isoformat(), 10),
            make_candle((today - timedelta(days=1)).isoformat(), 11),
            make_candle(today.isoformat(), 12),
        ]
        provider = StubProvider(candles=candles)
        self.assertEqual(ensure_history(self.share, days=5, provider=provider), 3)
        self.assertEqual(PriceSnapshot.objects.filter(share=self.share).count(), 4)

    def test_latest_price_falls_back_to_snapshot(self):
        self.assertIsNone(latest_price(self.share))
        make_snapshot(self.share, "77.5")
        self.assertEqual(latest_price(self.share), Decimal("77.500000"))
        self.share.last_price = Decimal("80")
        self.assertEqual(latest_price(self.share), Decimal("80"))


class RefreshAllIntegrationTests(TestCase):
    def test_refresh_triggers_alerts_and_strategies(self):
        from strategy.models import Strategy, StrategyRule
        from watchlist.models import PriceAlert, Watchlist, WatchlistItem

        share = make_share("INT", price=100)
        user = get_user_model().objects.create_user(
            username="int@example.com", email="int@example.com", password="x"
        )
        watchlist = Watchlist.objects.create(user=user, name="W")
        item = WatchlistItem.objects.create(watchlist=watchlist, share=share)
        PriceAlert.objects.create(
            item=item,
            condition=PriceAlert.Condition.ABOVE,
            target_price=Decimal("150"),
        )
        strategy = Strategy.objects.create(
            user=user,
            name="S",
            share=share,
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        StrategyRule.objects.create(
            strategy=strategy,
            side=StrategyRule.Side.BUY,
            condition=StrategyRule.Condition.BELOW,
            threshold=Decimal("1000"),
            quantity=Decimal("2"),
        )

        provider = StubProvider(make_quote(share, "160", timezone.now()))
        summary = refresh_all(provider=provider)

        self.assertEqual(summary["updated"], 1)
        self.assertEqual(item.alerts.get().notifications.count(), 1)
        self.assertEqual(strategy.trades.count(), 1)
