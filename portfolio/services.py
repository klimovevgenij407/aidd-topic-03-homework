"""Portfolio valuation and transaction validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError

from dashboard.models import Share
from portfolio.models import Portfolio, PortfolioTransaction

ZERO = Decimal("0")


class PortfolioError(ValueError):
    """Raised when stored transactions are inconsistent."""


@dataclass(frozen=True, slots=True)
class Position:
    share: Share
    quantity: Decimal
    average_price: Decimal
    last_price: Decimal | None
    cost_basis: Decimal
    market_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal

    @property
    def has_market_price(self) -> bool:
        return self.last_price is not None


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    portfolio: Portfolio
    positions: list[Position]
    total_cost_basis: Decimal
    total_market_value: Decimal
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_pnl: Decimal


def calculate_portfolio(portfolio: Portfolio) -> PortfolioSummary:
    transactions = list(
        portfolio.transactions.select_related("share").order_by("executed_at", "id")
    )
    states: dict[int, dict] = {}

    for transaction in transactions:
        state = states.setdefault(
            transaction.share_id,
            {
                "share": transaction.share,
                "quantity": ZERO,
                "average_price": ZERO,
                "realized_pnl": ZERO,
            },
        )
        if transaction.side == PortfolioTransaction.Side.BUY:
            new_quantity = state["quantity"] + transaction.quantity
            total_cost = (
                state["average_price"] * state["quantity"]
                + transaction.price * transaction.quantity
                + transaction.commission
            )
            state["quantity"] = new_quantity
            state["average_price"] = total_cost / new_quantity if new_quantity else ZERO
        else:
            if transaction.quantity > state["quantity"]:
                raise PortfolioError(
                    f"Продажа {transaction.quantity} {transaction.share.ticker} "
                    "превышает остаток на момент операции."
                )
            state["realized_pnl"] += (
                transaction.price - state["average_price"]
            ) * transaction.quantity - transaction.commission
            state["quantity"] -= transaction.quantity
            if state["quantity"] == 0:
                state["average_price"] = ZERO

    positions: list[Position] = []
    for state in states.values():
        if state["quantity"] == 0 and state["realized_pnl"] == 0:
            continue
        share = state["share"]
        quantity = state["quantity"]
        average_price = state["average_price"]
        last_price = share.last_price
        cost_basis = average_price * quantity
        market_value = (
            last_price if last_price is not None else average_price
        ) * quantity
        unrealized_pnl = market_value - cost_basis
        positions.append(
            Position(
                share=share,
                quantity=quantity,
                average_price=average_price,
                last_price=last_price,
                cost_basis=cost_basis,
                market_value=market_value,
                realized_pnl=state["realized_pnl"],
                unrealized_pnl=unrealized_pnl,
                total_pnl=state["realized_pnl"] + unrealized_pnl,
            )
        )

    positions.sort(key=lambda position: position.share.ticker)
    return PortfolioSummary(
        portfolio=portfolio,
        positions=positions,
        total_cost_basis=sum((p.cost_basis for p in positions), ZERO),
        total_market_value=sum((p.market_value for p in positions), ZERO),
        total_realized_pnl=sum((p.realized_pnl for p in positions), ZERO),
        total_unrealized_pnl=sum((p.unrealized_pnl for p in positions), ZERO),
        total_pnl=sum((p.total_pnl for p in positions), ZERO),
    )


def validate_transaction(
    portfolio: Portfolio,
    share: Share,
    side: str,
    quantity: Decimal,
    executed_at,
    *,
    exclude_pk: int | None = None,
) -> None:
    """Validate a sell against holdings at the operation time.

    The current implementation models a long-only portfolio: a sell cannot
    exceed the quantity held at that moment.
    """

    if side != PortfolioTransaction.Side.SELL:
        return

    transactions = portfolio.transactions.filter(share=share).order_by(
        "executed_at", "id"
    )
    if exclude_pk:
        transactions = transactions.exclude(pk=exclude_pk)

    held = ZERO
    for transaction in transactions:
        if transaction.executed_at > executed_at:
            break
        if transaction.side == PortfolioTransaction.Side.BUY:
            held += transaction.quantity
        else:
            held -= transaction.quantity
        if held < 0:
            raise ValidationError(
                "В истории операций уже есть продажа, превышающая остаток."
            )

    if quantity > held:
        raise ValidationError(
            f"Недостаточно акций: в наличии {held}, запрошено {quantity}."
        )
