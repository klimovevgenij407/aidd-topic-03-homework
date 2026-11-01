from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from dashboard.models import PriceSnapshot, Share
from strategy.models import Strategy, StrategyTrade
from strategy.services import calculate_state, evaluate_strategies, toggle_strategy

User = get_user_model()


def make_share(**overrides):
    defaults = {
        "figi": f"FIGI{uuid.uuid4().hex[:10]}",
        "isin": f"ISIN{uuid.uuid4().hex[:10]}",
        "name": "Сбербанк",
        "ticker": f"T{uuid.uuid4().hex[:6].upper()}",
        "currency": "rub",
        "last_price": Decimal("100.00"),
    }
    defaults.update(overrides)
    return Share.objects.create(**defaults)


class StrategyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="strategy@example.com",
            email="strategy@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="Стратегия",
            share=self.share,
            buy_below=Decimal("90"),
            sell_above=Decimal("120"),
            initial_cash=Decimal("1000"),
        )

    def snapshot(self, price, minutes=0):
        return PriceSnapshot.objects.create(
            share=self.share,
            price=Decimal(price),
            captured_at=timezone.now() + timedelta(minutes=minutes),
            source=PriceSnapshot.Source.SIMULATED,
        )

    def test_buy_and_sell_cycle(self):
        buy_trades = evaluate_strategies(self.snapshot("85"))
        self.assertEqual(len(buy_trades), 1)
        self.assertEqual(buy_trades[0].side, StrategyTrade.Side.BUY)
        self.assertGreater(buy_trades[0].quantity, 0)

        state = calculate_state(self.strategy)
        self.assertGreater(state.position, 0)
        self.assertLess(state.cash, Decimal("1"))

        self.share.last_price = Decimal("125")
        self.share.save(update_fields=["last_price"])
        sell_trades = evaluate_strategies(self.snapshot("125", 1))
        self.assertEqual(len(sell_trades), 1)
        self.assertEqual(sell_trades[0].side, StrategyTrade.Side.SELL)
        state = calculate_state(self.strategy)
        self.assertEqual(state.position, Decimal("0"))
        self.assertGreater(state.pnl, Decimal("0"))

    def test_duplicate_snapshot_does_not_duplicate_trade(self):
        snapshot = self.snapshot("85")
        evaluate_strategies(snapshot)
        evaluate_strategies(snapshot)
        self.assertEqual(self.strategy.trades.count(), 1)

    def test_inactive_strategy_is_skipped(self):
        toggle_strategy(self.strategy)
        self.assertEqual(evaluate_strategies(self.snapshot("85")), [])

    def test_fixed_quantity(self):
        self.strategy.quantity = Decimal("2")
        self.strategy.save(update_fields=["quantity"])
        evaluate_strategies(self.snapshot("85"))
        trade = self.strategy.trades.get()
        self.assertEqual(trade.quantity, Decimal("2"))

    def test_state_for_empty_strategy(self):
        state = calculate_state(self.strategy)
        self.assertEqual(state.equity, Decimal("1000"))
        self.assertEqual(state.pnl, Decimal("0"))
        self.assertEqual(state.return_percent, Decimal("0"))


class StrategyViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="Стратегия",
            share=self.share,
            buy_below=Decimal("90"),
            sell_above=Decimal("120"),
            initial_cash=Decimal("1000"),
        )

    def test_requires_login(self):
        response = self.client.get(reverse("strategy:strategy_list"))
        self.assertEqual(response.status_code, 302)

    def test_create_sets_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("strategy:strategy_create"),
            {
                "name": "Новая стратегия",
                "share": self.share.pk,
                "buy_below": "80",
                "sell_above": "130",
                "initial_cash": "1000",
                "quantity": "",
                "is_active": "on",
            },
        )
        self.assertRedirects(
            response,
            reverse(
                "strategy:strategy_detail",
                args=[Strategy.objects.get(name="Новая стратегия").pk],
            ),
        )
        self.assertEqual(
            Strategy.objects.get(name="Новая стратегия").user,
            self.user,
        )

    def test_invalid_thresholds(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("strategy:strategy_create"),
            {
                "name": "Плохая",
                "share": self.share.pk,
                "buy_below": "130",
                "sell_above": "120",
                "initial_cash": "1000",
                "quantity": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "должна быть выше")

    def test_other_user_cannot_open(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("strategy:strategy_detail", args=[self.strategy.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_toggle(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("strategy:strategy_toggle", args=[self.strategy.pk])
        )
        self.assertRedirects(
            response,
            reverse("strategy:strategy_detail", args=[self.strategy.pk]),
        )
        self.strategy.refresh_from_db()
        self.assertFalse(self.strategy.is_active)


class StrategyAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api-strategy@example.com",
            email="api-strategy@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()

    def test_create_and_state(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/strategies/",
            {
                "name": "API стратегия",
                "share": self.share.pk,
                "buy_below": "90",
                "sell_above": "120",
                "initial_cash": "1000",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        strategy_id = response.data["id"]

        response = self.client.get(f"/api/v1/strategies/{strategy_id}/state/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["position"], "0.000000")

        response = self.client.post(f"/api/v1/strategies/{strategy_id}/toggle/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_active"])
