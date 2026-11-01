from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.tests.factories import make_share, make_snapshot
from strategy.models import Strategy, StrategyRule, StrategyTrade

User = get_user_model()


class StrategyApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api@example.com", email="api@example.com", password="x"
        )
        self.other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="x"
        )
        self.share = make_share("SBER", price="90")
        self.snapshot = make_snapshot(self.share, "90")
        self.client.force_authenticate(self.user)

    def _create_strategy(self):
        return Strategy.objects.create(
            user=self.user,
            name="S",
            share=self.share,
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )

    def test_create_strategy_sets_cash(self):
        response = self.client.post(
            "/api/v1/strategies/",
            {
                "name": "S",
                "share": self.share.pk,
                "initial_cash": "1000.00",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        strategy = Strategy.objects.get(pk=response.data["id"])
        self.assertEqual(strategy.cash, Decimal("1000.00"))
        self.assertEqual(strategy.user, self.user)

    def test_add_rule_and_run(self):
        strategy = self._create_strategy()
        response = self.client.post(
            "/api/v1/strategy-rules/",
            {
                "strategy": strategy.pk,
                "side": "buy",
                "condition": "below",
                "threshold": "100",
                "quantity": "2",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(f"/api/v1/strategies/{strategy.pk}/run/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["executed"], 1)
        self.assertEqual(StrategyTrade.objects.count(), 1)

        response = self.client.get(f"/api/v1/strategies/{strategy.pk}/metrics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["trade_count"], 1)

    def test_foreign_strategy_hidden(self):
        foreign = Strategy.objects.create(
            user=self.other,
            name="secret",
            share=self.share,
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.get(f"/api/v1/strategies/{foreign.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(f"/api/v1/strategies/{foreign.pk}/metrics/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_add_rule_to_foreign_strategy(self):
        foreign = Strategy.objects.create(
            user=self.other,
            name="secret",
            share=self.share,
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.post(
            "/api/v1/strategy-rules/",
            {
                "strategy": foreign.pk,
                "side": "buy",
                "condition": "below",
                "threshold": "100",
                "quantity": "1",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trades_are_scoped(self):
        mine = self._create_strategy()
        foreign = Strategy.objects.create(
            user=self.other,
            name="secret",
            share=self.share,
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        rule = StrategyRule.objects.create(
            strategy=mine,
            side="buy",
            condition="below",
            threshold=Decimal("100"),
            quantity=Decimal("1"),
        )
        foreign_rule = StrategyRule.objects.create(
            strategy=foreign,
            side="buy",
            condition="below",
            threshold=Decimal("100"),
            quantity=Decimal("1"),
        )
        StrategyTrade.objects.create(
            strategy=mine,
            rule=rule,
            price_snapshot=self.snapshot,
            side="buy",
            quantity=1,
            price=90,
            cash_after=910,
            position_after=1,
        )
        StrategyTrade.objects.create(
            strategy=foreign,
            rule=foreign_rule,
            price_snapshot=self.snapshot,
            side="buy",
            quantity=1,
            price=90,
            cash_after=910,
            position_after=1,
        )
        response = self.client.get("/api/v1/strategy-trades/")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["strategy"], mine.pk)


class StrategyViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="html@example.com", email="html@example.com", password="pass12345"
        )
        self.share = make_share("SBER", price="90")
        self.snapshot = make_snapshot(self.share, "90")
        self.client.login(username="html@example.com", password="pass12345")

    def test_create_strategy_add_rule_and_run(self):
        response = self.client.post(
            "/strategies/",
            {"name": "S", "share": self.share.pk, "initial_cash": "1000"},
        )
        self.assertEqual(response.status_code, 302)
        strategy = Strategy.objects.get(user=self.user)

        response = self.client.post(
            f"/strategies/{strategy.pk}/",
            {
                "side": "buy",
                "condition": "below",
                "threshold": "100",
                "quantity": "2",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(strategy.rules.count(), 1)

        response = self.client.post(f"/strategies/{strategy.pk}/run/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(strategy.trades.count(), 1)

        response = self.client.get(f"/strategies/{strategy.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Журнал сделок")
