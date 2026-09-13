"""Update the price table from a saved vendor catalogue response.

The operator holds the credentials, not this tool, so a refresh reads a file
they produced with a documented command. The network never enters the path that
judges a plan.

Rows are edited in place, line by line, so comments and order survive and the
result is a diff a human can read: changed amounts, changed dates, nothing else
moved. Anything that could not be refreshed is named. A row that quietly kept
its old figure while looking fresh would be worse than no refresher at all.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

CATALOGUE_SOURCE = "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus"
NANOS = Decimal(1_000_000_000)
VALUE = re.compile(r'(?P<head>^\s*\w+\s*=\s*)"[^"]*"')


class RefreshError(Exception):
    """The catalogue response cannot be read."""


@dataclass
class RefreshReport:
    updated: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    unmatched: list[tuple[str, str]] = field(default_factory=list)
    unrefreshable: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines = []
        for label, keys in (("updated", self.updated), ("added", self.added)):
            for key in keys:
                lines.append(f"  {label:<15} {key}")
        for key, reason in self.unmatched:
            lines.append(f"  {'no match':<15} {key}: {reason}")
        for key in self.unrefreshable:
            lines.append(f"  {'no mapping':<15} {key}, left exactly as it was")
        return "\n".join(lines) or "  nothing to do"


def refresh_prices(
    path: Path, catalogue: Mapping[str, Any], *, today: date
) -> RefreshReport:
    text = Path(path).read_text(encoding="utf-8")
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RefreshError(f"{path} is not a readable price table: {exc}") from exc

    mappings = document.get("map", [])
    rows = {row.get("key"): row for row in document.get("price", [])}
    report = RefreshReport()
    resolved: dict[str, tuple[Decimal, str, str]] = {}

    for entry in mappings:
        key = str(entry.get("key", ""))
        found = _find(catalogue, entry)
        if isinstance(found, str):
            report.unmatched.append((key, found))
            continue
        amount, sku_id = found
        resolved[key] = (amount, sku_id, str(entry.get("unit", "")))
        (report.updated if key in rows else report.added).append(key)

    mapped = {str(entry.get("key", "")) for entry in mappings}
    report.unrefreshable = [key for key in rows if key not in mapped]

    Path(path).write_text(_rewrite(text, resolved, set(rows), today), encoding="utf-8")
    return report


def _find(catalogue: Mapping[str, Any], entry: Mapping[str, Any]) -> tuple[Decimal, str] | str:
    description = str(entry.get("description", "")).lower()
    region = str(entry.get("region", ""))
    for sku in catalogue.get("skus", []):
        if description not in str(sku.get("description", "")).lower():
            continue
        if region not in (sku.get("serviceRegions") or []):
            continue
        pricing = sku.get("pricingInfo") or []
        if not pricing:
            return "the matching SKU carries no pricingInfo"
        tiers = (pricing[-1].get("pricingExpression") or {}).get("tieredRates") or []
        priced = [tier for tier in tiers if _money(tier.get("unitPrice") or {}) != 0]
        if len(priced) != 1:
            return (
                f"priced in {len(tiers)} tiers, which cannot honestly become one rate"
            )
        return _money(priced[0]["unitPrice"]), str(sku.get("skuId", ""))
    return f"no SKU in the response matches {entry.get('description')!r} in {region}"


def _money(unit_price: Mapping[str, Any]) -> Decimal:
    units = Decimal(str(unit_price.get("units", "0") or "0"))
    nanos = Decimal(str(unit_price.get("nanos", 0) or 0))
    return units + nanos / NANOS


def _rewrite(
    text: str,
    resolved: Mapping[str, tuple[Decimal, str, str]],
    existing: set[str],
    today: date,
) -> str:
    lines = text.splitlines()
    out: list[str] = []
    key = ""
    in_price_row = False

    for line in lines:
        stripped = line.strip()
        if stripped == "[[price]]":
            in_price_row = True
            key = ""
        elif stripped.startswith("[["):
            in_price_row = False
            key = ""
        elif in_price_row and stripped.startswith("key"):
            key = stripped.split("=", 1)[1].strip().strip('"')

        if in_price_row and key in resolved:
            amount, sku_id, _ = resolved[key]
            field_name = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
            if field_name == "amount":
                line = _set(line, _plain(amount))
            elif field_name == "sku_id":
                line = _set(line, sku_id)
            elif field_name == "taken_on":
                line = _set(line, today.isoformat())
            elif field_name == "source":
                line = _set(line, CATALOGUE_SOURCE)
        out.append(line)

    added = [key for key in resolved if key not in existing]
    if added:
        out += ["", f"# Added by --refresh-prices on {today.isoformat()}, from the catalogue."]
        for key in added:
            amount, sku_id, unit = resolved[key]
            out += [
                "",
                "[[price]]",
                f'key      = "{key}"',
                f'unit     = "{unit}"',
                f'amount   = "{_plain(amount)}"',
                'currency = "USD"',
                f'region   = "{key.rsplit("/", 1)[-1]}"',
                f'source   = "{CATALOGUE_SOURCE}"',
                f'taken_on = "{today.isoformat()}"',
                f'sku_id   = "{sku_id}"',
            ]
    return "\n".join(out) + "\n"


def _set(line: str, value: str) -> str:
    return VALUE.sub(lambda match: f'{match.group("head")}"{value}"', line)


def _plain(amount: Decimal) -> str:
    return format(amount.normalize(), "f")
