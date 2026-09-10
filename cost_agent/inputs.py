"""Join the cost export to the inventory, keeping everything that fails to match.

An unpriced resource and unattributed spend are findings, not noise. Dropping
either understates the bill, which is the one number the whole analysis is
checked against.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class Resource:
    """A priced resource with its observable properties."""

    resource_id: str
    cloud: str
    service: str
    period_cost: Decimal
    kind: str
    tags: dict[str, str] = field(default_factory=dict)
    provisioned: float | None = None
    observed_peak: float | None = None
    utilisation_avg: float | None = None
    weekday_utilisation: float | None = None
    weekend_utilisation: float | None = None
    tier: str | None = None
    last_access: datetime | None = None
    age_days: int = 0
    attached: bool = True
    commitment_covered: bool = False


@dataclass(frozen=True)
class Unmatched:
    resource_id: str
    present_in: str  # "cost_export" or "inventory"
    period_cost: Decimal | None


@dataclass(frozen=True)
class Inputs:
    matched: tuple[Resource, ...]
    unmatched: tuple[Unmatched, ...]
    total_period_cost: Decimal


def _tags(raw: str) -> dict[str, str]:
    """`owner=platform;team=data` -> mapping. Empty string means no tags."""
    pairs = (pair for pair in raw.split(";") if "=" in pair)
    return dict(pair.split("=", 1) for pair in pairs)


def _when(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


def load_inputs(cost_export_path: Path, inventory_path: Path) -> Inputs:
    costs: dict[str, dict] = {}
    with Path(cost_export_path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            # Quantised once, here, so no float ever reaches the arithmetic.
            row["period_cost"] = Decimal(row["period_cost"]).quantize(CENTS)
            costs[row["resource_id"]] = row

    inventory = {
        item["resource_id"]: item
        for item in json.loads(Path(inventory_path).read_text())
    }

    matched, unmatched = [], []

    for resource_id, row in costs.items():
        item = inventory.get(resource_id)
        if item is None:
            unmatched.append(
                Unmatched(resource_id, "cost_export", row["period_cost"])
            )
            continue

        matched.append(
            Resource(
                resource_id=resource_id,
                cloud=row["cloud"],
                service=row["service"],
                period_cost=row["period_cost"],
                kind=item["kind"],
                tags=item.get("tags") or _tags(row.get("tags", "")),
                provisioned=item.get("provisioned"),
                observed_peak=item.get("observed_peak"),
                utilisation_avg=item.get("utilisation_avg"),
                weekday_utilisation=item.get("weekday_utilisation"),
                weekend_utilisation=item.get("weekend_utilisation"),
                tier=item.get("tier"),
                last_access=_when(item.get("last_access")),
                age_days=int(item.get("age_days", 0)),
                attached=bool(item.get("attached", True)),
                commitment_covered=bool(item.get("commitment_covered", False)),
            )
        )

    for resource_id in inventory:
        if resource_id not in costs:
            unmatched.append(Unmatched(resource_id, "inventory", None))

    return Inputs(
        matched=tuple(matched),
        unmatched=tuple(unmatched),
        total_period_cost=sum(
            (row["period_cost"] for row in costs.values()), Decimal("0")
        ),
    )
