"""Synchronously update latest prices (useful without a Celery worker)."""

from django.core.management.base import BaseCommand, CommandError

from dashboard.models import Share
from dashboard.services.market_data import MarketDataError
from dashboard.services.prices import update_share_prices


class Command(BaseCommand):
    help = "Fetch latest prices for all (or selected) shares"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            action="append",
            dest="tickers",
            default=[],
            help="Ticker to update; may be repeated",
        )

    def handle(self, *args, **options):
        shares = Share.objects.all()
        if options["tickers"]:
            shares = shares.filter(ticker__in=options["tickers"])

        try:
            updated = update_share_prices(list(shares))
        except MarketDataError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Updated shares: {updated}"))
