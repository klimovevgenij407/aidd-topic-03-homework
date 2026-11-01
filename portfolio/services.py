from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from market.services import latest_price
from portfolio.models import Portfolio, Position, Transaction

CASH_QUANT = Decimal("0.01")
PRICE_QUANT = Decimal("0.000001")


class TradeError(ValueError):
    """Операция не может быть выполнена."""


class InsufficientFunds(TradeError):
    pass


class InsufficientPosition(TradeError):
    pass


def _decimal(value, quant: Decimal) -> Decimal:
    return Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def execute_trade(
    portfolio: Portfolio,
    share,
    side: str,
    quantity,
    price,
    executed_at=None,
    note: str = "",
) -> Transaction:
    """Покупает или продаёт акции, обновляя позицию и свободные средства.

    Средняя цена покупки рассчитывается по методу средневзвешенной стоимости.
    Продажа не меняет среднюю цену, но фиксирует реализованный P&L.
    """

    qty = _decimal(quantity, PRICE_QUANT)
    trade_price = _decimal(price, PRICE_QUANT)
    if qty <= 0:
        raise TradeError("Количество должно быть больше нуля")
    if trade_price <= 0:
        raise TradeError("Цена должна быть больше нуля")
    if side not in (Transaction.Side.BUY, Transaction.Side.SELL):
        raise TradeError("Неизвестный тип операции")

    with transaction.atomic():
        portfolio = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
        position = (
            Position.objects.select_for_update()
            .filter(portfolio=portfolio, share=share)
            .first()
        )
        realized_pnl = Decimal("0.00")

        if side == Transaction.Side.BUY:
            cost = _decimal(qty * trade_price, CASH_QUANT)
            if cost > portfolio.cash:
                raise InsufficientFunds(
                    f"Недостаточно средств: нужно {cost}, доступно {portfolio.cash}"
                )
            if position:
                new_quantity = position.quantity + qty
                total_cost = position.quantity * position.avg_price + cost
                position.avg_price = _decimal(total_cost / new_quantity, PRICE_QUANT)
                position.quantity = new_quantity
                position.save(update_fields=["quantity", "avg_price"])
            else:
                Position.objects.create(
                    portfolio=portfolio,
                    share=share,
                    quantity=qty,
                    avg_price=trade_price,
                )
            portfolio.cash -= cost
        else:
            if position is None or position.quantity < qty:
                available = position.quantity if position else Decimal("0")
                raise InsufficientPosition(
                    f"Недостаточно акций: нужно {qty}, в портфеле {available}"
                )
            proceeds = _decimal(qty * trade_price, CASH_QUANT)
            realized_pnl = _decimal(
                (trade_price - position.avg_price) * qty, CASH_QUANT
            )
            position.quantity -= qty
            if position.quantity == 0:
                position.delete()
            else:
                position.save(update_fields=["quantity"])
            portfolio.cash += proceeds

        portfolio.save(update_fields=["cash"])
        return Transaction.objects.create(
            portfolio=portfolio,
            share=share,
            side=side,
            quantity=qty,
            price=trade_price,
            realized_pnl=realized_pnl,
            note=note,
            executed_at=executed_at or timezone.now(),
        )


def portfolio_valuation(portfolio: Portfolio) -> dict:
    """Текущая стоимость, нереализованная/реализованная прибыль и доходность."""

    rows = []
    market_value = Decimal("0")
    cost_basis = Decimal("0")
    unrealized = Decimal("0")

    positions = (
        Position.objects.filter(portfolio=portfolio)
        .select_related("share")
        .order_by("share__name")
    )
    for position in positions:
        price = latest_price(position.share) or position.avg_price
        value = _decimal(position.quantity * price, CASH_QUANT)
        cost = _decimal(position.quantity * position.avg_price, CASH_QUANT)
        pnl = value - cost
        rows.append(
            {
                "share": position.share,
                "quantity": position.quantity,
                "avg_price": position.avg_price,
                "current_price": price,
                "market_value": value,
                "cost_basis": cost,
                "unrealized_pnl": pnl,
            }
        )
        market_value += value
        cost_basis += cost
        unrealized += pnl

    realized = (
        Transaction.objects.filter(portfolio=portfolio).aggregate(
            total=Sum("realized_pnl")
        )["total"]
        or Decimal("0")
    )
    equity = portfolio.cash + market_value
    total_pnl = equity - portfolio.initial_cash
    return_pct = (
        (total_pnl / portfolio.initial_cash * 100)
        if portfolio.initial_cash
        else Decimal("0")
    )

    return {
        "positions": rows,
        "cash": portfolio.cash,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized,
        "realized_pnl": realized,
        "equity": equity,
        "initial_cash": portfolio.initial_cash,
        "total_pnl": total_pnl,
        "return_pct": return_pct,
    }
