"""The price table, which is the whole of what this tool believes things cost.

Two things fail at load rather than producing a number. A table holding two rows
for one key cannot be reviewed, because nobody can say which row a total used. A
table mixing currencies cannot be summed at all, and this tool does not convert.

Amounts are read as strings and kept as decimals. A float total invites a
rounding argument that has nothing to do with the analysis.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import cached_property
from pathlib import Path

from .registry import Unit

HOURS_PER_MONTH = Decimal(730)

REQUIRED = ("key", "unit", "amount", "currency", "region", "source", "taken_on")


class PriceError(Exception):
    """The table cannot be used. Never resolved by guessing a price."""


@dataclass(frozen=True)
class PriceRow:
    key: str
    unit: str
    amount: Decimal
    currency: str
    region: str
    source: str
    taken_on: date
    sku_id: str = ""


@dataclass(frozen=True)
class PriceTable:
    rows: tuple[PriceRow, ...]

    @cached_property
    def index(self) -> dict[str, PriceRow]:
        return {row.key: row for row in self.rows}

    def has(self, key: str) -> bool:
        return key in self.index

    def row(self, key: str) -> PriceRow:
        try:
            return self.index[key]
        except KeyError:
            raise PriceError(f"no price row for {key}") from None

    def monthly(self, unit: Unit) -> Decimal:
        """What this quantity costs for a month, at 730 hours to the month."""
        row = self.row(unit.key)
        per_month = row.amount * HOURS_PER_MONTH if row.unit == "hour" else row.amount
        return per_month * unit.quantity

    @property
    def oldest(self) -> date | None:
        return min((row.taken_on for row in self.rows), default=None)

    @property
    def currency(self) -> str:
        return self.rows[0].currency if self.rows else "USD"


def load_prices(path: Path) -> PriceTable:
    try:
        document = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PriceError(f"{path} could not be read as a price table: {exc}") from exc

    rows: list[PriceRow] = []
    seen: set[str] = set()
    currencies: set[str] = set()

    for raw in document.get("price", []):
        missing = [field for field in REQUIRED if not raw.get(field)]
        if missing:
            raise PriceError(f"a price row is missing {', '.join(missing)}: {raw}")
        key = str(raw["key"])
        if key in seen:
            raise PriceError(
                f"two rows carry the key {key}, so no reader can tell which one a total used"
            )
        seen.add(key)
        currencies.add(str(raw["currency"]))
        rows.append(
            PriceRow(
                key=key,
                unit=str(raw["unit"]),
                amount=_amount(raw["amount"], key),
                currency=str(raw["currency"]),
                region=str(raw["region"]),
                source=str(raw["source"]),
                taken_on=_taken_on(raw["taken_on"], key),
                sku_id=str(raw.get("sku_id", "")),
            )
        )

    if len(currencies) > 1:
        raise PriceError(
            f"the table mixes {' and '.join(sorted(currencies))}, and this tool does not convert"
        )
    return PriceTable(rows=tuple(rows))


def _amount(value: object, key: str) -> Decimal:
    if isinstance(value, float):
        raise PriceError(
            f"the amount for {key} is a float; quote it as a string so it stays exact"
        )
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise PriceError(f"the amount for {key} is not a number: {value!r}") from None


def _taken_on(value: object, key: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise PriceError(f"taken_on for {key} is not an ISO date: {value!r}") from None
