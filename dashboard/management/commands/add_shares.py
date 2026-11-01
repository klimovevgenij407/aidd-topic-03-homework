"""Import the T-Invest share universe into the local database."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dashboard.models import Share


class Command(BaseCommand):
    help = "Import shares from the T-Invest API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print instruments without writing them to the database",
        )

    def handle(self, *args, **options):
        if not settings.TINKOFF_TOKEN:
            raise CommandError(
                "TINKOFF_TOKEN is empty; set it in .env before importing shares"
            )

        try:
            from t_tech.invest import Client
        except ImportError as exc:
            raise CommandError(
                "t-tech-investments is not installed; "
                "install requirements-marketdata.txt"
            ) from exc

        created = updated = skipped = 0
        with Client(settings.TINKOFF_TOKEN) as client:
            response = client.instruments.shares()

        for instrument in response.instruments:
            defaults = {
                "name": instrument.name,
                "isin": instrument.isin,
                "ticker": instrument.ticker,
                "currency": instrument.currency,
                "uid": instrument.uid,
            }
            if options["dry_run"]:
                self.stdout.write(
                    f"{instrument.ticker:12} {instrument.figi:20} {instrument.name}"
                )
                continue
            try:
                _share, was_created = Share.objects.update_or_create(
                    figi=instrument.figi,
                    defaults=defaults,
                )
            except Exception as exc:
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipped {instrument.ticker} ({instrument.figi}): {exc}"
                    )
                )
                continue
            if was_created:
                created += 1
            else:
                updated += 1

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run finished"))
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Shares imported: created={created}, updated={updated}, "
                f"skipped={skipped}"
            )
        )
