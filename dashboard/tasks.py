"""Celery tasks for the dashboard."""

import logging

from config.celery import app
from dashboard.services.market_data import MarketDataError
from dashboard.services.prices import update_share_prices

logger = logging.getLogger(__name__)


@app.task(
    name="dashboard.tasks.update_last_price",
    autoretry_for=(MarketDataError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def update_last_price() -> int:
    """Update latest prices for all shares and return the updated count."""

    try:
        updated = update_share_prices()
    except MarketDataError:
        logger.exception("Market data update failed")
        raise
    logger.info("Market data update finished: %s shares updated", updated)
    return updated
