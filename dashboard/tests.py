from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import PriceSnapshot, Share
from dashboard.services.graph import get_graph
from dashboard.services.market_data import (
    MarketDataError,
    Quote,
    SimulatedProvider,
    TinkoffProvider,
    get_provider,
)
from dashboard.services.price_history import calculate_stats, ensure_price_history
from dashboard.services.prices import update_share_prices
from monitoring.models import Notification, Watchlist, WatchlistItem
from strategy.models import Strategy, StrategyTrade

User = get_user_model()


def make_share(**overrides):
    defaults = {
        "figi": f"FIGI{uuid.uuid4().hex[:10]}",
        "isin": f"ISIN{uuid.uuid4().hex[:10]}",
        "name": "Apple",
        "ticker": f"T{uuid.uuid4().hex[:8].upper()}",
        "currency": "usd",
        "last_price": Decimal("100.50"),
        "is_trend_high": True,
    }
    defaults.update(overrides)
    return Share.objects.create(**defaults)


class ShareModelTests(TestCase):
    def test_uid_is_generated_and_str_is_readable(self):
        share = make_share(ticker="AAPL", name="Apple Inc.")
        self.assertTrue(share.uid)
        self.assertEqual(str(share), "AAPL — Apple Inc.")

    def test_decimal_price_is_preserved(self):
        share = make_share(last_price=Decimal("123.456789"))
        share.refresh_from_db()
        self.assertEqual(share.last_price, Decimal("123.456789"))


class ShareWebViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.share = make_share(ticker="AAPL", name="Apple")
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )

    def test_list_is_public(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apple")

    def test_detail_is_public_and_builds_chart(self):
        response = self.client.get(reverse("dashboard:detail", args=[self.share.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apple")
        self.assertTrue(response.context["plot_div"])

    def test_detail_missing_returns_404(self):
        response = self.client.get(reverse("dashboard:detail", args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_open_create(self):
        response = self.client.get(reverse("dashboard:create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("user:auth"), response.url)

    def test_authenticated_user_can_create_update_and_delete(self):
        self.client.force_login(self.user)
        payload = {
            "figi": "BBG000B9XRY4",
            "isin": "US0378331005",
            "name": "Apple Inc.",
            "ticker": "aapl3",
            "currency": "USD",
        }
        response = self.client.post(reverse("dashboard:create"), payload)
        self.assertRedirects(response, reverse("dashboard:index"))
        share = Share.objects.get(figi="BBG000B9XRY4")
        self.assertEqual(share.ticker, "AAPL3")
        self.assertEqual(share.currency, "usd")
        self.assertTrue(share.uid)

        response = self.client.post(
            reverse("dashboard:update", args=[share.pk]),
            {**payload, "name": "Apple Updated"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        share.refresh_from_db()
        self.assertEqual(share.name, "Apple Updated")

        response = self.client.post(reverse("dashboard:delete", args=[share.pk]))
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertFalse(Share.objects.filter(pk=share.pk).exists())

    def test_invalid_create_does_not_create_share(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("dashboard:create"), {"ticker": "ZZZZ"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Share.objects.filter(ticker="ZZZZ").count(), 0)

    def test_chart_falls_back_to_message_when_provider_fails(self):
        with patch(
            "dashboard.views.get_history", side_effect=MarketDataError("no data")
        ):
            response = self.client.get(
                reverse("dashboard:detail", args=[self.share.pk])
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "График временно недоступен")
        self.assertEqual(response.context["plot_div"], "")


class AuthTests(TestCase):
    def test_registration_success_logs_user_in(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "NewUser@Example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.username, "newuser@example.com")
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_registration_password_mismatch(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "user@example.com",
                "password1": "StrongPass123!",
                "password2": "DifferentPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "пароли не совпадают")
        self.assertFalse(User.objects.filter(email="user@example.com").exists())

    def test_registration_duplicate_email_is_case_insensitive(self):
        User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "USER@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже зарегистрирован")

    def test_registration_weak_password_is_rejected(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "user@example.com",
                "password1": "123",
                "password2": "123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="user@example.com").exists())

    def test_registration_missing_field_does_not_crash(self):
        response = self.client.post(reverse("user:registration"), {"email": ""})
        self.assertEqual(response.status_code, 200)

    def test_login_success_with_uppercase_email(self):
        User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )
        response = self.client.post(
            reverse("user:auth"),
            {"email": "USER@example.com", "password": "StrongPass123!"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_login_failure_and_missing_fields(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "user@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")
        response = self.client.post(reverse("user:auth"), {})
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("user:logout"))
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ShareAPITests(APITestCase):
    def setUp(self):
        self.share = make_share(ticker="AAPL", name="Apple")
        self.user = User.objects.create_user(
            username="api@example.com",
            email="api@example.com",
            password="StrongPass123!",
        )
        self.payload = {
            "figi": "BBG000B9XRY4",
            "isin": "US0378331005",
            "name": "Apple Inc.",
            "ticker": "AAPL2",
            "currency": "usd",
        }

    def test_public_read(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_write(self):
        response = self.client.post("/api/v1/shares/", self.payload, format="json")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_authenticated_create_generates_uid(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/api/v1/shares/", self.payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["uid"])
        self.assertEqual(response.data["ticker"], "AAPL2")

    def test_authenticated_update_and_validation(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            f"/api/v1/shares/{self.share.pk}/",
            {"name": "Apple Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Apple Updated")
        response = self.client.patch(
            f"/api/v1/shares/{self.share.pk}/",
            {"name": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authenticated_delete_and_missing(self):
        self.client.force_authenticate(self.user)
        response = self.client.delete(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.delete(f"/api/v1/shares/{self.share.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_search_and_ordering(self):
        make_share(ticker="MSFT", name="Microsoft", figi="BBG000BPH459")
        response = self.client.get("/api/v1/shares/?ticker=AAPL")
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get("/api/v1/shares/?search=Micro")
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get("/api/v1/shares/?ordering=name")
        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, sorted(names))


class FakeProvider:
    def __init__(self, price=None, candles=None, error=None):
        self.price = price
        self.candles = candles or []
        self.error = error

    def get_last_quotes(self, shares):
        if self.error:
            raise self.error
        return {
            share.figi: Quote(
                figi=share.figi,
                price=self.price,
                at=timezone.now(),
                source="simulated",
            )
            for share in shares
        }

    def get_daily_candles(self, share, days=180):
        return self.candles


class PriceServiceTests(TestCase):
    def setUp(self):
        self.share = make_share(last_price=Decimal("100.00"))

    def test_update_price_sets_trend_and_updated_at(self):
        old_updated_at = timezone.now() - timedelta(days=1)
        Share.objects.filter(pk=self.share.pk).update(updated_at=old_updated_at)
        provider = FakeProvider(price=Decimal("110.00"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            updated = update_share_prices()
        self.assertEqual(updated, 1)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal("110.00"))
        self.assertTrue(self.share.is_trend_high)
        self.assertGreater(self.share.updated_at, old_updated_at)

    def test_equal_or_lower_price_is_not_growth(self):
        provider = FakeProvider(price=Decimal("100.00"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            update_share_prices()
        self.share.refresh_from_db()
        self.assertFalse(self.share.is_trend_high)

        provider = FakeProvider(price=Decimal("90.00"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            update_share_prices()
        self.share.refresh_from_db()
        self.assertFalse(self.share.is_trend_high)

    def test_provider_error_is_propagated(self):
        provider = FakeProvider(error=MarketDataError("offline"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            with self.assertRaises(MarketDataError):
                update_share_prices()

    def test_tick_prices_command(self):
        provider = FakeProvider(price=Decimal("111.00"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            call_command("tick_prices", "--ticker", self.share.ticker)
        self.share.refresh_from_db()
        self.assertEqual(self.share.last_price, Decimal("111.00"))


class MarketDataProviderTests(TestCase):
    def setUp(self):
        self.share = make_share(last_price=Decimal("100.00"))

    def test_simulated_provider_is_deterministic_for_candles(self):
        provider = SimulatedProvider()
        candles = provider.get_daily_candles(self.share, days=10)
        self.assertEqual(len(candles), 10)
        self.assertTrue(all(candle.close > 0 for candle in candles))
        self.assertEqual(candles[-1].close, Decimal("100.000000000"))

    def test_simulated_quote(self):
        provider = SimulatedProvider()
        quotes = provider.get_last_quotes([self.share])
        self.assertIn(self.share.figi, quotes)
        self.assertGreater(quotes[self.share.figi].price, 0)
        self.assertEqual(quotes[self.share.figi].source, "simulated")

    def test_get_provider_modes(self):
        self.assertIsInstance(get_provider("simulated"), SimulatedProvider)
        with self.assertRaises(MarketDataError):
            get_provider("unknown")

    @override_settings(TINKOFF_TOKEN="token")
    def test_tinkoff_quotation_is_converted_with_nano(self):
        quotation = SimpleNamespace(units=12, nano=345000000)
        last_price = SimpleNamespace(
            figi=self.share.figi,
            price=quotation,
            time=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
        )
        response = SimpleNamespace(last_prices=[last_price])

        class FakeMarketData:
            def get_last_prices(self, figi):
                self.figi = figi
                return response

        class FakeClient:
            def __init__(self, token):
                self.token = token
                self.market_data = FakeMarketData()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_quotation_to_decimal(value):
            return Decimal(value.units) + Decimal(value.nano) / Decimal(1_000_000_000)

        provider = TinkoffProvider("token")
        with patch.object(
            TinkoffProvider,
            "_sdk",
            return_value=(
                FakeClient,
                None,
                lambda: timezone.now(),
                fake_quotation_to_decimal,
            ),
        ):
            quotes = provider.get_last_quotes([self.share])
        self.assertEqual(quotes[self.share.figi].price, Decimal("12.345000000"))

    @override_settings(TINKOFF_TOKEN="token")
    def test_tinkoff_candles_are_converted(self):
        candles = [
            SimpleNamespace(
                time=datetime(2026, 1, 1, tzinfo=UTC),
                close=SimpleNamespace(units=100, nano=500000000),
            )
        ]

        class FakeClient:
            def __init__(self, token):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def get_all_candles(self, **kwargs):
                return candles

        def fake_quotation_to_decimal(value):
            return Decimal(value.units) + Decimal(value.nano) / Decimal(1_000_000_000)

        class FakeCandleInterval:
            CANDLE_INTERVAL_DAY = "day"

        provider = TinkoffProvider("token")
        with patch.object(
            TinkoffProvider,
            "_sdk",
            return_value=(
                FakeClient,
                FakeCandleInterval,
                lambda: timezone.now(),
                fake_quotation_to_decimal,
            ),
        ):
            result = provider.get_daily_candles(self.share)
        self.assertEqual(result[0].close, Decimal("100.500000000"))

    def test_graph_returns_html(self):
        cache.clear()
        result = get_graph(self.share, days=7)
        self.assertIn("plotly", result.lower())


class AddSharesCommandTests(TestCase):
    @override_settings(TINKOFF_TOKEN="token")
    def test_import_is_idempotent_and_updates_existing(self):
        instrument = SimpleNamespace(
            figi="FIGI-TEST",
            isin="ISIN-TEST",
            name="Old name",
            ticker="TEST",
            currency="rub",
            uid="UID-TEST",
        )

        class FakeInstruments:
            def shares(self):
                return SimpleNamespace(instruments=[instrument])

        class FakeClient:
            def __init__(self, token):
                self.instruments = FakeInstruments()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("t_tech.invest.Client", FakeClient):
            call_command("add_shares")
        self.assertEqual(Share.objects.count(), 1)
        self.assertEqual(Share.objects.get().name, "Old name")

        instrument.name = "New name"
        with patch("t_tech.invest.Client", FakeClient):
            call_command("add_shares")
        self.assertEqual(Share.objects.count(), 1)
        self.assertEqual(Share.objects.get().name, "New name")


class PriceHistoryTests(TestCase):
    def setUp(self):
        self.share = make_share(last_price=Decimal("100.00"))

    def test_stats(self):
        snapshots = [
            PriceSnapshot.objects.create(
                share=self.share,
                price=Decimal("100"),
                captured_at=timezone.now() - timedelta(days=2),
            ),
            PriceSnapshot.objects.create(
                share=self.share,
                price=Decimal("110"),
                captured_at=timezone.now() - timedelta(days=1),
            ),
            PriceSnapshot.objects.create(
                share=self.share,
                price=Decimal("105"),
                captured_at=timezone.now(),
            ),
        ]
        stats = calculate_stats(snapshots)
        self.assertEqual(stats.first, Decimal("100"))
        self.assertEqual(stats.last, Decimal("105"))
        self.assertEqual(stats.absolute_change, Decimal("5"))
        self.assertEqual(stats.percent_change, Decimal("5"))
        self.assertEqual(stats.minimum, Decimal("100"))
        self.assertEqual(stats.maximum, Decimal("110"))
        self.assertEqual(stats.count, 3)

    def test_empty_stats(self):
        self.assertIsNone(calculate_stats([]))

    def test_ensure_history_creates_snapshots(self):
        snapshots = ensure_price_history(self.share, days=30)
        self.assertGreaterEqual(len(snapshots), 20)
        self.assertTrue(
            PriceSnapshot.objects.filter(
                share=self.share,
                source=PriceSnapshot.Source.HISTORY,
            ).exists()
        )


class PriceUpdatePipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pipeline@example.com",
            email="pipeline@example.com",
            password="StrongPass123!",
        )
        self.share = make_share(last_price=Decimal("100.00"))
        self.watchlist = Watchlist.objects.create(user=self.user, name="Список")
        self.item = WatchlistItem.objects.create(
            watchlist=self.watchlist,
            share=self.share,
            target_price=Decimal("105"),
            direction=WatchlistItem.Direction.ABOVE,
        )
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="Стратегия",
            share=self.share,
            buy_below=Decimal("95"),
            sell_above=Decimal("120"),
            initial_cash=Decimal("1000"),
        )

    def test_update_creates_snapshot_and_triggers_features(self):
        provider = FakeProvider(price=Decimal("110"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            update_share_prices()
        self.assertEqual(PriceSnapshot.objects.filter(share=self.share).count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(self.strategy.trades.count(), 0)

        provider = FakeProvider(price=Decimal("90"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            update_share_prices()
        self.assertEqual(PriceSnapshot.objects.filter(share=self.share).count(), 2)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(self.strategy.trades.count(), 1)
        self.assertEqual(self.strategy.trades.get().side, StrategyTrade.Side.BUY)

        provider = FakeProvider(price=Decimal("125"))
        with patch("dashboard.services.prices.get_provider", return_value=provider):
            update_share_prices()
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(self.strategy.trades.count(), 2)
        self.assertEqual(self.strategy.trades.last().side, StrategyTrade.Side.SELL)


class ShareHistoryAPITests(APITestCase):
    def test_history_endpoint(self):
        share = make_share(last_price=Decimal("100.00"))
        response = self.client.get(f"/api/v1/shares/{share.pk}/history/?days=7")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 7)
        self.assertGreater(response.data["stats"]["count"], 0)
        self.assertTrue(response.data["points"])

    def test_history_invalid_days_falls_back(self):
        share = make_share(last_price=Decimal("100.00"))
        response = self.client.get(f"/api/v1/shares/{share.pk}/history/?days=999")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 180)
