"""Monthly figures for a parsed plan.

A deletion is a credit and a replacement is a difference. Both are easy to get
wrong in the direction that overstates cost, which would make the tool loudest
about exactly the changes worth encouraging.

Only resources the coverage step put in the priced bucket appear here. Everything
else is counted there and named in the report, never folded into the total as a
zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .coverage import Bucket, Summary, summarise
from .plan import Action, ResourceChange
from .prices import PriceTable
from .registry import Unit

ZERO = Decimal(0)


@dataclass(frozen=True)
class Line:
    address: str
    resource_type: str
    action: Action
    before: Decimal
    after: Decimal
    at_minimum: bool
    detail: str

    @property
    def delta(self) -> Decimal:
        return self.after - self.before


@dataclass(frozen=True)
class PricedPlan:
    lines: list[Line]
    coverage: Summary
    total: Decimal
    has_figure: bool


def price_plan(changes: Sequence[ResourceChange], table: PriceTable) -> PricedPlan:
    coverage = summarise(changes, has_row=table.has)
    lines: list[Line] = []

    for change, bucket, before_units, after_units in zip(
        changes, coverage.buckets, coverage.before, coverage.after, strict=True
    ):
        if bucket is not Bucket.PRICED:
            continue
        before = sum((table.monthly(unit) for unit in before_units), ZERO)
        after = sum((table.monthly(unit) for unit in after_units), ZERO)
        lines.append(
            Line(
                address=change.address,
                resource_type=change.type,
                action=change.action,
                before=before,
                after=after,
                at_minimum=any(unit.at_minimum for unit in before_units + after_units),
                detail=_detail(before_units, after_units),
            )
        )

    return PricedPlan(
        lines=lines,
        coverage=coverage,
        total=sum((line.delta for line in lines), ZERO),
        has_figure=bool(lines),
    )


def _detail(before: tuple[Unit, ...], after: tuple[Unit, ...]) -> str:
    """What was priced, in the words of the price keys that priced it."""
    if before and after:
        return f"{_describe(before)} to {_describe(after)}"
    if after:
        return _describe(after)
    return f"{_describe(before)}, removed"


def _describe(units: tuple[Unit, ...]) -> str:
    return ", ".join(_describe_one(unit) for unit in units)


def _describe_one(unit: Unit) -> str:
    parts = unit.key.split("/")
    shape, name, region = parts[1], parts[2], parts[-1]
    quantity = f"{unit.quantity.normalize():f}"
    if shape == "disk":
        return f"{quantity} GB {name}, {region}"
    at_minimum = " at minimum" if unit.at_minimum else ""
    return f"{quantity} x {name}{at_minimum}, {region}"
