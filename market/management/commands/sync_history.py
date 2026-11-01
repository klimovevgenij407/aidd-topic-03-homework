from django.conf import settings
from django.core.management.base import BaseCommand

from dashboard.models import Share
from market.services import ensure_history


class Command(BaseCommand):
    help = "Backfill daily price history for all shares"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=getattr(settings, "MARKET_DATA_HISTORY_DAYS", 180),
            help="History depth in days",
        )

    def handle(self, *args, **options):
        days = options["days"]
        total = 0
        for share in Share.objects.all():
            added = ensure_history(share, days=days)
            total += added
            self.stdout.write(f"{share.ticker}: +{added}")
        self.stdout.write(
            self.style.SUCCESS(f"Добавлено снимков: {total} (за {days} дней)")
        )
