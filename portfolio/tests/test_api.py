from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.tests.factories import make_share
from portfolio.models import Portfolio, Position, Transaction

User = get_user_model()


class PortfolioApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api@example.com", email="api@example.com", password="x"
        )
        self.other = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="x"
        )
        self.share = make_share("SBER", price="100")
        self.client.force_authenticate(self.user)

    def test_create_portfolio_sets_cash(self):
        response = self.client.post(
            "/api/v1/portfolios/",
            {"name": "P", "initial_cash": "1000.00"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        portfolio = Portfolio.objects.get(pk=response.data["id"])
        self.assertEqual(portfolio.user, self.user)
        self.assertEqual(portfolio.cash, Decimal("1000.00"))

    def test_trade_and_valuation(self):
        portfolio = Portfolio.objects.create(
            user=self.user,
            name="P",
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.post(
            f"/api/v1/portfolios/{portfolio.pk}/trades/",
            {"share": self.share.pk, "side": "buy", "quantity": "2", "price": "100"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)

        self.share.last_price = Decimal("110")
        self.share.save(update_fields=["last_price"])
        response = self.client.get(
            f"/api/v1/portfolios/{portfolio.pk}/valuation/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(float(response.data["equity"]), 1020.0)
        self.assertAlmostEqual(float(response.data["total_pnl"]), 20.0)
        self.assertEqual(len(response.data["positions"]), 1)

    def test_trade_uses_market_price_when_omitted(self):
        portfolio = Portfolio.objects.create(
            user=self.user,
            name="P",
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.post(
            f"/api/v1/portfolios/{portfolio.pk}/trades/",
            {"share": self.share.pk, "side": "buy", "quantity": "1"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Position.objects.get(portfolio=portfolio).avg_price, Decimal("100")
        )

    def test_oversell_returns_400(self):
        portfolio = Portfolio.objects.create(
            user=self.user,
            name="P",
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.post(
            f"/api/v1/portfolios/{portfolio.pk}/trades/",
            {"share": self.share.pk, "side": "sell", "quantity": "1", "price": "100"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_foreign_portfolio_is_hidden(self):
        foreign = Portfolio.objects.create(
            user=self.other,
            name="secret",
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        response = self.client.get(f"/api/v1/portfolios/{foreign.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.get(f"/api/v1/portfolios/{foreign.pk}/valuation/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_transactions_are_scoped(self):
        mine = Portfolio.objects.create(
            user=self.user,
            name="mine",
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        foreign = Portfolio.objects.create(
            user=self.other,
            name="foreign",
            initial_cash=Decimal("1000"),
            cash=Decimal("1000"),
        )
        Transaction.objects.create(
            portfolio=mine, share=self.share, side="buy", quantity=1, price=100
        )
        Transaction.objects.create(
            portfolio=foreign, share=self.share, side="buy", quantity=1, price=100
        )
        response = self.client.get("/api/v1/transactions/")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["portfolio"], mine.pk)


class PortfolioViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="html@example.com", email="html@example.com", password="pass12345"
        )
        self.share = make_share("SBER", price="100")
        self.client.login(username="html@example.com", password="pass12345")

    def test_create_portfolio_and_trade_via_html(self):
        response = self.client.post(
            "/portfolios/", {"name": "P", "initial_cash": "1000.00"}
        )
        self.assertEqual(response.status_code, 302)
        portfolio = Portfolio.objects.get(user=self.user)

        response = self.client.post(
            f"/portfolios/{portfolio.pk}/",
            {"share": self.share.pk, "side": "buy", "quantity": "2", "price": "100"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 1)

        response = self.client.get(f"/portfolios/{portfolio.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1000,00")

    def test_trade_error_is_shown(self):
        portfolio = Portfolio.objects.create(
            user=self.user,
            name="P",
            initial_cash=Decimal("100"),
            cash=Decimal("100"),
        )
        response = self.client.post(
            f"/portfolios/{portfolio.pk}/",
            {"share": self.share.pk, "side": "buy", "quantity": "2", "price": "100"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Недостаточно средств")
        self.assertEqual(Transaction.objects.count(), 0)
