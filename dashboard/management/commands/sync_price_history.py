"""Backfill daily price history for existing shares."""

from django.core.management.base import BaseCommand, CommandError

from dashboard.models import Share
from dashboard.services.market_data import MarketDataError
from dashboard.services.price_history import ensure_price_history


class Command(BaseCommand):
    help = "Fetch daily price history for shares"

    def add_arguments(self, parser):
        parser.add_argument("--ticker", action="append", dest="tickers", default=[])
        parser.add_argument("--days", type=int, default=180)

    def handle(self, *args, **options):
        shares = Share.objects.all()
        if options["tickers"]:
            shares = shares.filter(ticker__in=options["tickers"])

        total = 0
        for share in shares:
            try:
                snapshots = ensure_price_history(
                    share,
                    days=options["days"],
                    force=True,
                )
            except MarketDataError as exc:
                raise CommandError(f"{share.ticker}: {exc}") from exc
            total += len(snapshots)
            self.stdout.write(f"{share.ticker}: {len(snapshots)} snapshots")
        self.stdout.write(self.style.SUCCESS(f"History points: {total}"))
