"""Celery application and beat schedule for periodic market data updates."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {
    "update-market-prices-every-5-minutes": {
        "task": "dashboard.tasks.update_last_price",
        "schedule": 300.0,
    },
}
