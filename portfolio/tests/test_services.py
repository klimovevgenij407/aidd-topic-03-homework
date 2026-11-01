from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from dashboard.tests.factories import make_share
from portfolio.models import Portfolio, Position, Transaction
from portfolio.services import (
    InsufficientFunds,
    InsufficientPosition,
    TradeError,
    execute_trade,
    portfolio_valuation,
)

User = get_user_model()


class PortfolioServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="p@example.com", email="p@example.com", password="x"
        )
        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="P",
            initial_cash=Decimal("1000.00"),
            cash=Decimal("1000.00"),
        )
        self.share = make_share("SBER", price="100")

    def test_buy_creates_position_and_updates_cash(self):
        trade = execute_trade(self.portfolio, self.share, "buy", 3, "100.50")
        self.portfolio.refresh_from_db()
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(self.portfolio.cash, Decimal("698.50"))
        self.assertEqual(position.quantity, Decimal("3.000000"))
        self.assertEqual(position.avg_price, Decimal("100.500000"))
        self.assertEqual(trade.realized_pnl, Decimal("0.00"))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_second_buy_uses_weighted_average(self):
        execute_trade(self.portfolio, self.share, "buy", 3, "100.50")
        execute_trade(self.portfolio, self.share, "buy", 2, "120")
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("5.000000"))
        self.assertEqual(position.avg_price, Decimal("108.300000"))

    def test_sell_updates_cash_and_realized_pnl(self):
        execute_trade(self.portfolio, self.share, "buy", 3, "100.50")
        execute_trade(self.portfolio, self.share, "buy", 2, "120")
        trade = execute_trade(self.portfolio, self.share, "sell", 2, "130")
        self.portfolio.refresh_from_db()
        position = Position.objects.get(portfolio=self.portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("3.000000"))
        self.assertEqual(position.avg_price, Decimal("108.300000"))
        self.assertEqual(self.portfolio.cash, Decimal("718.50"))
        self.assertEqual(trade.realized_pnl, Decimal("43.40"))

    def test_full_sell_removes_position(self):
        execute_trade(self.portfolio, self.share, "buy", 2, "100")
        execute_trade(self.portfolio, self.share, "sell", 2, "110")
        self.assertFalse(
            Position.objects.filter(portfolio=self.portfolio, share=self.share).exists()
        )

    def test_insufficient_funds_rolls_back(self):
        with self.assertRaises(InsufficientFunds):
            execute_trade(self.portfolio, self.share, "buy", 20, "100")
        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash, Decimal("1000.00"))
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertFalse(Position.objects.exists())

    def test_oversell_rolls_back(self):
        execute_trade(self.portfolio, self.share, "buy", 1, "100")
        with self.assertRaises(InsufficientPosition):
            execute_trade(self.portfolio, self.share, "sell", 2, "100")
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(
            Position.objects.get(portfolio=self.portfolio).quantity, Decimal("1.000000")
        )

    def test_invalid_values(self):
        with self.assertRaises(TradeError):
            execute_trade(self.portfolio, self.share, "buy", 0, "100")
        with self.assertRaises(TradeError):
            execute_trade(self.portfolio, self.share, "hold", 1, "100")

    def test_valuation(self):
        execute_trade(self.portfolio, self.share, "buy", 2, "100")
        self.portfolio.refresh_from_db()
        self.share.last_price = Decimal("120")
        self.share.save(update_fields=["last_price"])
        valuation = portfolio_valuation(self.portfolio)
        self.assertEqual(valuation["cash"], Decimal("800.00"))
        self.assertEqual(valuation["market_value"], Decimal("240.00"))
        self.assertEqual(valuation["equity"], Decimal("1040.00"))
        self.assertEqual(valuation["total_pnl"], Decimal("40.00"))
        self.assertEqual(valuation["unrealized_pnl"], Decimal("40.00"))
        self.assertEqual(valuation["return_pct"], Decimal("4.0000"))
