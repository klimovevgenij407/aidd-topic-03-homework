"""Set a share price manually and run the feature pipeline (demo helper)."""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from dashboard.models import PriceSnapshot, Share
from dashboard.services.prices import process_price_snapshot


class Command(BaseCommand):
    help = "Set a share price and trigger watchlist/strategy evaluation"

    def add_arguments(self, parser):
        parser.add_argument("--ticker", required=True)
        parser.add_argument("--price", required=True)

    def handle(self, *args, **options):
        try:
            price = Decimal(options["price"])
        except InvalidOperation as exc:
            raise CommandError("--price must be a decimal number") from exc
        if price <= 0:
            raise CommandError("--price must be positive")

        try:
            share = Share.objects.get(ticker=options["ticker"].upper())
        except Share.DoesNotExist as exc:
            raise CommandError(f"Share {options['ticker']} not found") from exc

        previous = share.last_price
        share.last_price = price
        share.is_trend_high = None if previous is None else price > previous
        share.save(update_fields=["last_price", "is_trend_high", "updated_at"])

        snapshot = PriceSnapshot.objects.create(
            share=share,
            price=price,
            captured_at=timezone.now(),
            source=PriceSnapshot.Source.SIMULATED,
        )
        process_price_snapshot(snapshot)
        self.stdout.write(
            self.style.SUCCESS(
                f"{share.ticker}: {previous} -> {price}; snapshot {snapshot.pk}"
            )
        )
