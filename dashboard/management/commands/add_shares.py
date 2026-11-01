from django.core.management.base import BaseCommand

from dashboard.models import Share
from market.providers import get_provider


class Command(BaseCommand):
    help = "Add or update shares from the configured market data provider"

    def handle(self, *args, **options):
        provider = get_provider()
        created, updated = 0, 0
        for instrument in provider.list_instruments():
            _, is_created = Share.objects.update_or_create(
                figi=instrument.figi,
                defaults={
                    "isin": instrument.isin,
                    "name": instrument.name,
                    "ticker": instrument.ticker,
                    "currency": instrument.currency,
                    "uid": instrument.uid,
                },
            )
            created += int(is_created)
            updated += int(not is_created)
        self.stdout.write(
            self.style.SUCCESS(
                f"Провайдер {provider.name}: создано {created}, обновлено {updated}"
            )
        )
