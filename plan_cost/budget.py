"""A threshold taken from the organisation's own budget.

The budget API has no per-change threshold, so this derives one: the budget
amount times its lowest threshold percentage, which is the point the
organisation itself chose to be told about spend. One change consuming a whole
alert band is a defensible line to draw, and the report shows the arithmetic so
a reader can draw it somewhere else.

What this cannot do is know current spend. That needs the billing export, which
is a different data source, so the tool judges one change in isolation and says
so rather than implying it knows the account is clear.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

NANOS = Decimal(1_000_000_000)


class BudgetError(Exception):
    """No threshold can be derived. Never resolved by picking a number."""


@dataclass(frozen=True)
class Threshold:
    monthly: Decimal
    derivation: str
    applies_to: str
    budget: str


def threshold_from(document: Mapping[str, Any], *, name: str | None = None) -> Threshold:
    budgets = document.get("budgets") or []
    if not budgets:
        raise BudgetError("the response holds no budgets")

    budget = _select(budgets, name)
    display = str(budget.get("displayName", "unnamed"))

    amount = budget.get("amount") or {}
    if "specifiedAmount" not in amount:
        raise BudgetError(
            f"budget {display!r} is set to lastPeriodAmount, which carries no figure in "
            "the response, so no threshold can be derived from it"
        )
    total = _money(amount["specifiedAmount"])

    rules = budget.get("thresholdRules") or []
    percents = [
        Decimal(str(rule.get("thresholdPercent")))
        for rule in rules
        if rule.get("thresholdPercent") is not None
    ]
    if not percents:
        raise BudgetError(
            f"budget {display!r} sets no thresholdRules, so it names no line to judge against"
        )
    lowest = min(percents)

    return Threshold(
        monthly=total * lowest,
        derivation=(
            f'budget "{display}": ${total:,.2f} x {(lowest * 100).normalize()}% '
            f"= ${total * lowest:,.2f}. Current spend is unknown to this tool, so this "
            "judges the change on its own"
        ),
        applies_to=_filter(budget.get("budgetFilter") or {}),
        budget=display,
    )


def _select(budgets: list[Mapping[str, Any]], name: str | None) -> Mapping[str, Any]:
    if name is not None:
        for budget in budgets:
            if str(budget.get("displayName", "")) == name:
                return budget
        held = ", ".join(str(b.get("displayName", "unnamed")) for b in budgets)
        raise BudgetError(f"no budget named {name!r}; the response holds {held}")
    if len(budgets) == 1:
        return budgets[0]
    held = ", ".join(str(b.get("displayName", "unnamed")) for b in budgets)
    raise BudgetError(
        f"the response holds {len(budgets)} budgets ({held}); name one with --budget-name "
        "rather than having this tool pick"
    )


def _money(specified: Mapping[str, Any]) -> Decimal:
    units = Decimal(str(specified.get("units", "0") or "0"))
    nanos = Decimal(str(specified.get("nanos", 0) or 0))
    return units + nanos / NANOS


def _filter(budget_filter: Mapping[str, Any]) -> str:
    """What the budget covers, printed so a reader can see whether it covers this plan."""
    parts: list[str] = []
    projects = budget_filter.get("projects") or []
    if projects:
        parts.append(", ".join(str(project) for project in projects))
    services = budget_filter.get("services") or []
    if services:
        parts.append(f"{len(services)} services")
    period = budget_filter.get("calendarPeriod")
    if period:
        parts.append(f"calendar period {period}")
    return "; ".join(parts) if parts else "no filter stated"
