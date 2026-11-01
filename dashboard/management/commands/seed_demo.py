from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from dashboard.models import Share
from market.models import PriceSnapshot
from market.providers import SyntheticProvider
from market.services import ensure_history, refresh_share
from portfolio.models import Portfolio
from portfolio.services import execute_trade
from strategy.models import Strategy, StrategyRule
from strategy.services import evaluate_strategy
from watchlist.models import PriceAlert, Watchlist, WatchlistItem
from watchlist.services import process_share_alerts

User = get_user_model()


class Command(BaseCommand):
    help = "Create an idempotent offline demo: user, shares, history, alerts, portfolio, strategy"

    def handle(self, *args, **options):
        provider = SyntheticProvider()
        with transaction.atomic():
            user, _ = User.objects.get_or_create(
                username="demo@example.com",
                defaults={"email": "demo@example.com"},
            )
            user.email = "demo@example.com"
            user.set_password("demo12345")
            user.save(update_fields=["email", "password"])

            shares = {}
            for instrument in provider.list_instruments():
                share, _ = Share.objects.update_or_create(
                    figi=instrument.figi,
                    defaults={
                        "isin": instrument.isin,
                        "name": instrument.name,
                        "ticker": instrument.ticker,
                        "currency": instrument.currency,
                        "uid": instrument.uid,
                    },
                )
                shares[share.ticker] = share

            for share in shares.values():
                ensure_history(share, days=180, provider=provider)
                refresh_share(share, provider=provider)

            watchlist, _ = Watchlist.objects.get_or_create(
                user=user, name="Мой список"
            )
            for ticker in ("SBER", "GAZP"):
                item, _ = WatchlistItem.objects.get_or_create(
                    watchlist=watchlist,
                    share=shares[ticker],
                    defaults={"note": "Демонстрационная позиция"},
                )
                if not item.alerts.exists():
                    current = shares[ticker].last_price or Decimal("100")
                    PriceAlert.objects.create(
                        item=item,
                        condition=PriceAlert.Condition.ABOVE,
                        target_price=(current * Decimal("0.995")).quantize(
                            Decimal("0.000001")
                        ),
                    )

            for ticker in ("SBER", "GAZP"):
                snapshot = (
                    PriceSnapshot.objects.filter(share=shares[ticker])
                    .order_by("-captured_at")
                    .first()
                )
                if snapshot:
                    process_share_alerts(shares[ticker], snapshot)

            portfolio, created = Portfolio.objects.get_or_create(
                user=user,
                name="Демо-портфель",
                defaults={
                    "initial_cash": Decimal("1000000.00"),
                    "cash": Decimal("1000000.00"),
                },
            )
            if created:
                for ticker, quantity in (("SBER", Decimal("100")), ("GAZP", Decimal("50"))):
                    share = shares[ticker]
                    price = share.last_price or Decimal("100")
                    execute_trade(
                        portfolio,
                        share,
                        "buy",
                        quantity,
                        price,
                        note="Демонстрационная покупка",
                    )

            strategy, created = Strategy.objects.get_or_create(
                user=user,
                name="SBER: покупать на текущем уровне",
                defaults={
                    "share": shares["SBER"],
                    "initial_cash": Decimal("100000.00"),
                    "cash": Decimal("100000.00"),
                },
            )
            if created:
                current = shares["SBER"].last_price or Decimal("100")
                StrategyRule.objects.create(
                    strategy=strategy,
                    side=StrategyRule.Side.BUY,
                    condition=StrategyRule.Condition.BELOW,
                    threshold=(current * Decimal("1.01")).quantize(
                        Decimal("0.000001")
                    ),
                    quantity=Decimal("10"),
                )
                StrategyRule.objects.create(
                    strategy=strategy,
                    side=StrategyRule.Side.SELL,
                    condition=StrategyRule.Condition.ABOVE,
                    threshold=(current * Decimal("1.05")).quantize(
                        Decimal("0.000001")
                    ),
                    quantity=Decimal("10"),
                )
                snapshot = (
                    PriceSnapshot.objects.filter(share=shares["SBER"])
                    .order_by("-captured_at")
                    .first()
                )
                if snapshot:
                    evaluate_strategy(strategy, snapshot)

        self.stdout.write(self.style.SUCCESS("Демо-данные готовы."))
        self.stdout.write("Вход: demo@example.com / demo12345")
        self.stdout.write(f"Акций: {len(shares)}, портфель: {portfolio.name}")
