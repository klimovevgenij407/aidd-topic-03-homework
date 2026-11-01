"""Seed a complete demo dataset without external services."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dashboard.models import PriceSnapshot, Share
from dashboard.services.market_data import SimulatedProvider
from monitoring.models import Watchlist, WatchlistItem
from portfolio.models import Portfolio, PortfolioTransaction
from strategy.models import Strategy

User = get_user_model()

DEMO_SHARES = (
    {
        "figi": "BBG004730N88",
        "isin": "RU0009029540",
        "name": "Сбербанк",
        "ticker": "SBER",
        "currency": "rub",
        "uid": "e6123145-9665-43e0-8413-cd61b8aa9b13",
    },
    {
        "figi": "BBG004730RP0",
        "isin": "RU0007661625",
        "name": "Газпром",
        "ticker": "GAZP",
        "currency": "rub",
        "uid": "962e2a95-02a9-4171-abd7-aa198dbf3d9a",
    },
    {
        "figi": "BBG004731032",
        "isin": "RU0009024277",
        "name": "Лукойл",
        "ticker": "LKOH",
        "currency": "rub",
        "uid": "6b2f9a6a-5b8a-4d5e-9f0f-8f1a4c5d6e7f",
    },
    {
        "figi": "BBG006L8G4H1",
        "isin": "NL0009805522",
        "name": "Яндекс",
        "ticker": "YDEX",
        "currency": "rub",
        "uid": "8a4f9e3d-2c1b-4a5f-9e8d-7c6b5a4f3e2d",
    },
)


class Command(BaseCommand):
    help = "Create demo shares, price history, user, watchlist, portfolio and strategy"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=180,
            help="Number of daily price points to generate (default: 180)",
        )

    def handle(self, *args, **options):
        days = max(30, options["days"])
        provider = SimulatedProvider()

        with transaction.atomic():
            shares = []
            for data in DEMO_SHARES:
                share, _created = Share.objects.update_or_create(
                    figi=data["figi"],
                    defaults=data,
                )
                shares.append(share)

            for share in shares:
                candles = provider.get_daily_candles(share, days=days)
                PriceSnapshot.objects.bulk_create(
                    [
                        PriceSnapshot(
                            share=share,
                            price=candle.close,
                            captured_at=candle.at,
                            source=PriceSnapshot.Source.HISTORY,
                        )
                        for candle in candles
                    ],
                    ignore_conflicts=True,
                )
                latest = (
                    PriceSnapshot.objects.filter(share=share)
                    .order_by("-captured_at")
                    .first()
                )
                if latest:
                    previous = (
                        PriceSnapshot.objects.filter(
                            share=share,
                            captured_at__lt=latest.captured_at,
                        )
                        .order_by("-captured_at")
                        .first()
                    )
                    share.last_price = latest.price
                    share.is_trend_high = (
                        None if previous is None else latest.price > previous.price
                    )
                    share.save(
                        update_fields=["last_price", "is_trend_high", "updated_at"]
                    )

            demo_user, user_created = User.objects.get_or_create(
                username="demo@example.com",
                defaults={"email": "demo@example.com"},
            )
            demo_user.email = "demo@example.com"
            demo_user.set_password("demo12345")
            demo_user.save()
            if user_created:
                self.stdout.write("Demo user created: demo@example.com / demo12345")

            watchlist, _ = Watchlist.objects.get_or_create(
                user=demo_user,
                name="Мой список",
            )
            sber = Share.objects.get(ticker="SBER")
            gazp = Share.objects.get(ticker="GAZP")
            WatchlistItem.objects.get_or_create(
                watchlist=watchlist,
                share=sber,
                defaults={
                    "target_price": (sber.last_price or Decimal("100"))
                    * Decimal("1.05"),
                    "direction": WatchlistItem.Direction.ABOVE,
                },
            )
            WatchlistItem.objects.get_or_create(
                watchlist=watchlist,
                share=gazp,
                defaults={
                    "target_price": (gazp.last_price or Decimal("100"))
                    * Decimal("0.95"),
                    "direction": WatchlistItem.Direction.BELOW,
                },
            )

            portfolio, _ = Portfolio.objects.get_or_create(
                user=demo_user,
                name="Демо-портфель",
                defaults={"base_currency": "rub"},
            )
            now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
            transactions = (
                (
                    sber,
                    PortfolioTransaction.Side.BUY,
                    Decimal("10"),
                    Decimal("0.90"),
                    10,
                    90,
                ),
                (
                    sber,
                    PortfolioTransaction.Side.BUY,
                    Decimal("5"),
                    Decimal("0.95"),
                    5,
                    60,
                ),
                (
                    sber,
                    PortfolioTransaction.Side.SELL,
                    Decimal("3"),
                    Decimal("1.02"),
                    0,
                    45,
                ),
                (
                    gazp,
                    PortfolioTransaction.Side.BUY,
                    Decimal("20"),
                    Decimal("0.94"),
                    12,
                    30,
                ),
            )
            PortfolioTransaction.objects.filter(
                portfolio=portfolio,
                note="Демо-операция",
            ).delete()
            for share, side, quantity, factor, commission, days_ago in transactions:
                price = (share.last_price or Decimal("100")) * factor
                PortfolioTransaction.objects.create(
                    portfolio=portfolio,
                    share=share,
                    side=side,
                    quantity=quantity,
                    price=price,
                    commission=Decimal(commission),
                    executed_at=now - timedelta(days=days_ago),
                    note="Демо-операция",
                )

            Strategy.objects.update_or_create(
                user=demo_user,
                name="Демо-стратегия SBER",
                defaults={
                    "share": sber,
                    "buy_below": (sber.last_price or Decimal("100")) * Decimal("0.95"),
                    "sell_above": (sber.last_price or Decimal("100")) * Decimal("1.05"),
                    "initial_cash": Decimal("100000"),
                    "quantity": None,
                    "is_active": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {len(shares)} shares, {days} days of history. "
                "Login: demo@example.com / demo12345"
            )
        )
