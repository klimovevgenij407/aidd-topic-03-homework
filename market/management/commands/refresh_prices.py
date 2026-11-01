from django.core.management.base import BaseCommand

from market.services import refresh_all


class Command(BaseCommand):
    help = "Refresh prices, save snapshots and evaluate alerts/strategies"

    def handle(self, *args, **options):
        summary = refresh_all()
        self.stdout.write(
            self.style.SUCCESS(
                "Обновлено: {updated}, ошибок: {errors}, снимков: {snapshots}".format(
                    **summary
                )
            )
        )
