"""Strategy evaluation and virtual trade journal."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from django.db import transaction

from dashboard.models import PriceSnapshot
from strategy.models import Strategy, StrategyTrade

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class StrategyState:
    cash: Decimal
    position: Decimal
    last_price: Decimal | None
    equity: Decimal
    pnl: Decimal
    return_percent: Decimal | None
    trades_count: int


def calculate_state(strategy: Strategy) -> StrategyState:
    trades = list(strategy.trades.all().order_by("executed_at", "id"))
    cash = strategy.initial_cash
    position = ZERO
    last_trade_price = None

    for trade in trades:
        last_trade_price = trade.price
        if trade.side == StrategyTrade.Side.BUY:
            cash -= trade.price * trade.quantity
            position += trade.quantity
        else:
            cash += trade.price * trade.quantity
            position -= trade.quantity

    last_price = strategy.share.last_price or last_trade_price
    equity = cash + (position * last_price if last_price is not None else ZERO)
    pnl = equity - strategy.initial_cash
    return StrategyState(
        cash=cash,
        position=position,
        last_price=last_price,
        equity=equity,
        pnl=pnl,
        return_percent=(
            pnl / strategy.initial_cash * Decimal("100")
            if strategy.initial_cash
            else None
        ),
        trades_count=len(trades),
    )


def _buy_quantity(strategy: Strategy, state: StrategyState, price: Decimal) -> Decimal:
    if strategy.quantity is not None:
        quantity = strategy.quantity
    else:
        quantity = (state.cash / price).quantize(
            Decimal("0.000001"),
            rounding=ROUND_DOWN,
        )
    if quantity <= 0 or quantity * price > state.cash:
        return ZERO
    return quantity


def evaluate_strategies(snapshot: PriceSnapshot) -> list[StrategyTrade]:
    """Evaluate active strategies for the snapshot's share.

    The simulator buys when there is no position and the price is at or below
    the buy threshold. It sells the whole position when the price is at or above
    the sell threshold. The unique constraint on (strategy, snapshot, side)
    prevents duplicate trades if the same snapshot is processed twice.
    """

    strategies = Strategy.objects.select_related("share").filter(
        share=snapshot.share,
        is_active=True,
    )
    created_trades: list[StrategyTrade] = []

    for strategy in strategies:
        state = calculate_state(strategy)
        if state.position == 0 and snapshot.price <= strategy.buy_below:
            quantity = _buy_quantity(strategy, state, snapshot.price)
            if quantity <= 0:
                continue
            with transaction.atomic():
                trade, created = StrategyTrade.objects.get_or_create(
                    strategy=strategy,
                    price_snapshot=snapshot,
                    side=StrategyTrade.Side.BUY,
                    defaults={
                        "price": snapshot.price,
                        "quantity": quantity,
                        "executed_at": snapshot.captured_at,
                        "reason": (
                            f"Цена {snapshot.price} ≤ порога покупки "
                            f"{strategy.buy_below}"
                        ),
                    },
                )
            if created:
                created_trades.append(trade)
        elif state.position > 0 and snapshot.price >= strategy.sell_above:
            with transaction.atomic():
                trade, created = StrategyTrade.objects.get_or_create(
                    strategy=strategy,
                    price_snapshot=snapshot,
                    side=StrategyTrade.Side.SELL,
                    defaults={
                        "price": snapshot.price,
                        "quantity": state.position,
                        "executed_at": snapshot.captured_at,
                        "reason": (
                            f"Цена {snapshot.price} ≥ порога продажи "
                            f"{strategy.sell_above}"
                        ),
                    },
                )
            if created:
                created_trades.append(trade)

    return created_trades


def toggle_strategy(strategy: Strategy) -> Strategy:
    strategy.is_active = not strategy.is_active
    strategy.save(update_fields=["is_active"])
    return strategy
