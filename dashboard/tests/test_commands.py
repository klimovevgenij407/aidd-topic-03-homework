import io

from django.core.management import call_command
from django.test import TestCase

from dashboard.models import Share
from portfolio.models import Portfolio, Transaction
from strategy.models import Strategy, StrategyTrade
from watchlist.models import Notification, PriceAlert


class AddSharesCommandTests(TestCase):
    def test_add_shares_is_idempotent_and_updates_existing(self):
        out = io.StringIO()
        call_command("add_shares", stdout=out)
        self.assertEqual(Share.objects.count(), 5)

        sber = Share.objects.get(ticker="SBER")
        sber.name = "Broken name"
        sber.save(update_fields=["name"])

        call_command("add_shares", stdout=out)
        self.assertEqual(Share.objects.count(), 5)
        sber.refresh_from_db()
        self.assertEqual(sber.name, "Сбербанк")


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_creates_full_dataset_and_is_idempotent(self):
        out = io.StringIO()
        call_command("seed_demo", stdout=out)

        self.assertEqual(Share.objects.count(), 5)
        self.assertEqual(Portfolio.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Strategy.objects.count(), 1)
        self.assertEqual(StrategyTrade.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(PriceAlert.objects.count(), 2)

        call_command("seed_demo", stdout=out)
        self.assertEqual(Share.objects.count(), 5)
        self.assertEqual(Portfolio.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(StrategyTrade.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
