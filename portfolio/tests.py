from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from dashboard.models import Share
from portfolio.models import Portfolio, PortfolioTransaction
from portfolio.services import calculate_portfolio, validate_transaction

User = get_user_model()


def make_share(**overrides):
    defaults = {
        "figi": f"FIGI{uuid.uuid4().hex[:10]}",
        "isin": f"ISIN{uuid.uuid4().hex[:10]}",
        "name": "Сбербанк",
        "ticker": f"P{uuid.uuid4().hex[:6].upper()}",
        "currency": "rub",
        "last_price": Decimal("125.00"),
    }
    defaults.update(overrides)
    return Share.objects.create(**defaults)


class PortfolioServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="portfolio@example.com",
            email="portfolio@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()
        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Портфель",
        )

    def add(self, side, quantity, price, commission="0", executed_at=None):
        return PortfolioTransaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=side,
            quantity=Decimal(quantity),
            price=Decimal(price),
            commission=Decimal(commission),
            executed_at=executed_at or timezone.now(),
        )

    def test_average_cost_and_pnl(self):
        self.add(PortfolioTransaction.Side.BUY, "10", "100", "10")
        self.add(PortfolioTransaction.Side.BUY, "10", "120", "10")
        summary = calculate_portfolio(self.portfolio)
        position = summary.positions[0]
        self.assertEqual(position.quantity, Decimal("20"))
        self.assertEqual(position.average_price, Decimal("111"))

        self.add(PortfolioTransaction.Side.SELL, "5", "130", "5")
        summary = calculate_portfolio(self.portfolio)
        position = summary.positions[0]
        self.assertEqual(position.quantity, Decimal("15"))
        self.assertEqual(position.realized_pnl, Decimal("90"))
        self.assertEqual(position.average_price, Decimal("111"))
        self.assertEqual(position.market_value, Decimal("1875"))
        self.assertEqual(position.unrealized_pnl, Decimal("210"))
        self.assertEqual(position.total_pnl, Decimal("300"))

    def test_sell_validation_rejects_oversell(self):
        self.add(PortfolioTransaction.Side.BUY, "5", "100")
        with self.assertRaises(ValidationError):
            validate_transaction(
                self.portfolio,
                self.share,
                PortfolioTransaction.Side.SELL,
                Decimal("6"),
                timezone.now(),
            )
        validate_transaction(
            self.portfolio,
            self.share,
            PortfolioTransaction.Side.SELL,
            Decimal("5"),
            timezone.now(),
        )

    def test_current_price_fallback(self):
        self.share.last_price = None
        self.share.save(update_fields=["last_price"])
        self.add(PortfolioTransaction.Side.BUY, "2", "100")
        summary = calculate_portfolio(self.portfolio)
        position = summary.positions[0]
        self.assertEqual(position.market_value, Decimal("200"))
        self.assertEqual(position.unrealized_pnl, Decimal("0"))


class PortfolioViewTests(TestCase):
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
        self.portfolio = Portfolio.objects.create(user=self.user, name="Портфель")

    def test_requires_login(self):
        response = self.client.get(reverse("portfolio:portfolio_list"))
        self.assertEqual(response.status_code, 302)

    def test_create_sets_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("portfolio:portfolio_create"),
            {"name": "Новый портфель", "base_currency": "rub"},
        )
        self.assertRedirects(
            response,
            reverse(
                "portfolio:portfolio_detail",
                args=[Portfolio.objects.get(name="Новый портфель").pk],
            ),
        )
        self.assertEqual(
            Portfolio.objects.get(name="Новый портфель").user,
            self.user,
        )

    def test_other_user_cannot_open_portfolio(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("portfolio:portfolio_detail", args=[self.portfolio.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_add_buy_transaction(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "portfolio:transaction_create",
                args=[self.portfolio.pk],
            ),
            {
                "share": self.share.pk,
                "side": PortfolioTransaction.Side.BUY,
                "quantity": "10",
                "price": "100",
                "commission": "0",
                "executed_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("portfolio:portfolio_detail", args=[self.portfolio.pk]),
        )
        self.assertEqual(self.portfolio.transactions.count(), 1)

    def test_invalid_sell_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse(
                "portfolio:transaction_create",
                args=[self.portfolio.pk],
            ),
            {
                "share": self.share.pk,
                "side": PortfolioTransaction.Side.SELL,
                "quantity": "10",
                "price": "100",
                "commission": "0",
                "executed_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Недостаточно акций")
        self.assertEqual(self.portfolio.transactions.count(), 0)

    def test_detail_renders_summary(self):
        PortfolioTransaction.objects.create(
            portfolio=self.portfolio,
            share=self.share,
            side=PortfolioTransaction.Side.BUY,
            quantity=Decimal("4"),
            price=Decimal("100"),
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("portfolio:portfolio_detail", args=[self.portfolio.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Позиции")
        self.assertContains(response, "500,00")


class PortfolioAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api-portfolio@example.com",
            email="api-portfolio@example.com",
            password="StrongPass123!",
        )
        self.share = make_share()

    def test_create_summary_and_transaction(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/portfolios/",
            {"name": "API портфель", "base_currency": "rub"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        portfolio_id = response.data["id"]

        response = self.client.post(
            "/api/v1/portfolio-transactions/",
            {
                "portfolio": portfolio_id,
                "share": self.share.pk,
                "side": PortfolioTransaction.Side.BUY,
                "quantity": "2",
                "price": "100",
                "commission": "0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        response = self.client.get(f"/api/v1/portfolios/{portfolio_id}/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_market_value"], "250.000000000")

    def test_invalid_sell(self):
        self.client.force_authenticate(self.user)
        portfolio = Portfolio.objects.create(user=self.user, name="Портфель")
        response = self.client.post(
            "/api/v1/portfolio-transactions/",
            {
                "portfolio": portfolio.pk,
                "share": self.share.pk,
                "side": PortfolioTransaction.Side.SELL,
                "quantity": "1",
                "price": "100",
                "commission": "0",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
