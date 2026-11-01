from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from dashboard.tests.factories import make_share, make_snapshot
from strategy.models import Strategy, StrategyRule, StrategyTrade
from strategy.services import (
    evaluate_strategy,
    process_share_strategies,
    strategy_metrics,
)

User = get_user_model()


class StrategyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="s@example.com", email="s@example.com", password="x"
        )
        self.share = make_share("SBER", price="90")
        self.strategy = Strategy.objects.create(
            user=self.user,
            name="S",
            share=self.share,
            initial_cash=Decimal("1000.00"),
            cash=Decimal("1000.00"),
        )
        self.buy_rule = StrategyRule.objects.create(
            strategy=self.strategy,
            side=StrategyRule.Side.BUY,
            condition=StrategyRule.Condition.BELOW,
            threshold=Decimal("100"),
            quantity=Decimal("2"),
        )
        self.snapshot = make_snapshot(self.share, "90")

    def test_buy_executes_once_per_snapshot(self):
        trades = evaluate_strategy(self.strategy, self.snapshot)
        self.assertEqual(len(trades), 1)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.cash, Decimal("820.00"))
        self.assertEqual(self.strategy.quantity, Decimal("2.000000"))
        self.assertEqual(self.strategy.avg_price, Decimal("90.000000"))
        self.assertEqual(evaluate_strategy(self.strategy, self.snapshot), [])

    def test_sell_records_realized_pnl(self):
        evaluate_strategy(self.strategy, self.snapshot)
        StrategyRule.objects.create(
            strategy=self.strategy,
            side=StrategyRule.Side.SELL,
            condition=StrategyRule.Condition.ABOVE,
            threshold=Decimal("120"),
            quantity=Decimal("1"),
        )
        sell_snapshot = make_snapshot(
            self.share, "130", timezone.now() + timedelta(minutes=1)
        )
        trades = evaluate_strategy(self.strategy, sell_snapshot)
        self.assertEqual(len(trades), 1)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.quantity, Decimal("1.000000"))
        self.assertEqual(self.strategy.cash, Decimal("950.00"))
        self.assertEqual(self.strategy.realized_pnl, Decimal("40.00"))

    def test_insufficient_cash_skips_trade(self):
        self.strategy.cash = Decimal("100.00")
        self.strategy.save(update_fields=["cash"])
        self.assertEqual(evaluate_strategy(self.strategy, self.snapshot), [])
        self.assertEqual(StrategyTrade.objects.count(), 0)

    def test_insufficient_position_skips_sell(self):
        self.buy_rule.is_active = False
        self.buy_rule.save(update_fields=["is_active"])
        StrategyRule.objects.create(
            strategy=self.strategy,
            side=StrategyRule.Side.SELL,
            condition=StrategyRule.Condition.ABOVE,
            threshold=Decimal("10"),
            quantity=Decimal("1"),
        )
        self.assertEqual(evaluate_strategy(self.strategy, self.snapshot), [])
        self.assertEqual(StrategyTrade.objects.count(), 0)

    def test_inactive_strategy_does_nothing(self):
        self.strategy.is_active = False
        self.strategy.save(update_fields=["is_active"])
        self.assertEqual(evaluate_strategy(self.strategy, self.snapshot), [])

    def test_process_share_strategies(self):
        self.assertEqual(process_share_strategies(self.share, self.snapshot), 1)
        self.assertEqual(process_share_strategies(self.share, self.snapshot), 0)

    def test_metrics(self):
        evaluate_strategy(self.strategy, self.snapshot)
        self.strategy.refresh_from_db()
        self.share.last_price = Decimal("100")
        self.share.save(update_fields=["last_price"])
        metrics = strategy_metrics(self.strategy)
        self.assertEqual(metrics["market_value"], Decimal("200.00"))
        self.assertEqual(metrics["equity"], Decimal("1020.00"))
        self.assertEqual(metrics["total_pnl"], Decimal("20.00"))
        self.assertEqual(metrics["return_pct"], Decimal("2"))
        self.assertEqual(metrics["unrealized_pnl"], Decimal("20.00"))
        self.assertEqual(metrics["trade_count"], 1)
