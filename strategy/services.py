from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from config.settings import logger
from market.services import latest_price
from strategy.models import Strategy, StrategyRule, StrategyTrade

CASH_QUANT = Decimal("0.01")
PRICE_QUANT = Decimal("0.000001")


def _decimal(value, quant: Decimal) -> Decimal:
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def evaluate_strategy(strategy: Strategy, snapshot, price=None) -> list[StrategyTrade]:
    """Применяет активные правила стратегии к одному снимку цены.

    Одна и та же пара (правило, снимок) обрабатывается не более одного раза,
    поэтому повторные запуски задачи не дублируют сделки.
    """

    trade_price = _decimal(price if price is not None else snapshot.price, PRICE_QUANT)
    executed: list[StrategyTrade] = []

    with transaction.atomic():
        strategy = Strategy.objects.select_for_update().get(pk=strategy.pk)
        if not strategy.is_active:
            return []

        rules = list(strategy.rules.filter(is_active=True).order_by("id"))
        for rule in rules:
            if not rule.condition_met(trade_price):
                continue
            if StrategyTrade.objects.filter(
                strategy=strategy, rule=rule, price_snapshot=snapshot
            ).exists():
                continue

            quantity = _decimal(rule.quantity, PRICE_QUANT)
            if quantity <= 0:
                continue
            realized = Decimal("0.00")

            if rule.side == StrategyRule.Side.BUY:
                cost = _decimal(quantity * trade_price, CASH_QUANT)
                if cost > strategy.cash:
                    logger.info(
                        "Стратегия %s: недостаточно средств для покупки %s",
                        strategy.pk,
                        quantity,
                    )
                    continue
                new_quantity = strategy.quantity + quantity
                total_cost = strategy.quantity * strategy.avg_price + cost
                strategy.avg_price = _decimal(total_cost / new_quantity, PRICE_QUANT)
                strategy.quantity = new_quantity
                strategy.cash -= cost
            else:
                if strategy.quantity < quantity:
                    logger.info(
                        "Стратегия %s: недостаточно акций для продажи %s",
                        strategy.pk,
                        quantity,
                    )
                    continue
                proceeds = _decimal(quantity * trade_price, CASH_QUANT)
                realized = _decimal(
                    (trade_price - strategy.avg_price) * quantity, CASH_QUANT
                )
                strategy.quantity -= quantity
                strategy.cash += proceeds
                strategy.realized_pnl += realized
                if strategy.quantity == 0:
                    strategy.avg_price = Decimal("0")

            strategy.save(
                update_fields=[
                    "cash",
                    "quantity",
                    "avg_price",
                    "realized_pnl",
                ]
            )
            executed.append(
                StrategyTrade.objects.create(
                    strategy=strategy,
                    rule=rule,
                    price_snapshot=snapshot,
                    side=rule.side,
                    quantity=quantity,
                    price=trade_price,
                    realized_pnl=realized,
                    cash_after=strategy.cash,
                    position_after=strategy.quantity,
                )
            )
    return executed


def process_share_strategies(share, snapshot) -> int:
    """Запускает все активные стратегии по акции на новом снимке цены."""

    total = 0
    for strategy in Strategy.objects.filter(share=share, is_active=True):
        try:
            total += len(evaluate_strategy(strategy, snapshot))
        except Exception as exc:  # noqa: BLE001 - одна стратегия не ломает задачу
            logger.error("Ошибка стратегии %s: %s", strategy.pk, exc)
    return total


def run_strategy_now(strategy: Strategy) -> list[StrategyTrade]:
    """Ручной запуск на последнем снимке (или на свежей котировке)."""

    from market.models import PriceSnapshot
    from market.services import refresh_share

    snapshot = (
        PriceSnapshot.objects.filter(share=strategy.share)
        .order_by("-captured_at")
        .first()
    )
    if snapshot is None:
        snapshot = refresh_share(strategy.share).snapshot
    return evaluate_strategy(strategy, snapshot)


def strategy_metrics(strategy: Strategy) -> dict:
    price = latest_price(strategy.share) or strategy.avg_price or Decimal("0")
    market_value = _decimal(strategy.quantity * price, CASH_QUANT)
    equity = strategy.cash + market_value
    unrealized = (
        _decimal((price - strategy.avg_price) * strategy.quantity, CASH_QUANT)
        if strategy.quantity
        else Decimal("0.00")
    )
    total_pnl = equity - strategy.initial_cash
    return_pct = (
        (total_pnl / strategy.initial_cash * 100)
        if strategy.initial_cash
        else Decimal("0")
    )
    trade_count = StrategyTrade.objects.filter(strategy=strategy).count()
    return {
        "cash": strategy.cash,
        "quantity": strategy.quantity,
        "avg_price": strategy.avg_price,
        "current_price": price,
        "market_value": market_value,
        "equity": equity,
        "unrealized_pnl": unrealized,
        "realized_pnl": strategy.realized_pnl,
        "total_pnl": total_pnl,
        "return_pct": return_pct,
        "trade_count": trade_count,
    }
