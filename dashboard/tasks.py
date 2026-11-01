from celery import shared_task

from market.services import refresh_all


@shared_task
def update_last_price() -> dict:
    """Устаревшее имя задачи, сохранено для совместимости."""

    return refresh_all()
