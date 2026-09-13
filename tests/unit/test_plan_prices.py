"""The price table.

Two refusals matter more than the arithmetic. A table holding two rows for one
key cannot be reviewed, because nobody can tell which one the total used. A
table mixing currencies cannot be summed at all, and this tool does not convert.
Both fail at load rather than producing a number.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from plan_cost.prices import HOURS_PER_MONTH, PriceError, load_prices
from plan_cost.registry import Unit

SHIPPED = Path(__file__).resolve().parents[2] / "plan_cost" / "prices.toml"


def a_table(tmp_path, body):
    path = tmp_path / "prices.toml"
    path.write_text(body, encoding="utf-8")
    return load_prices(path)


ROW = """
[[price]]
key      = "google/machine-type/e2-standard-4/us-central1"
unit     = "hour"
amount   = "0.134"
currency = "USD"
region   = "us-central1"
source   = "https://example.test/e2-standard-4"
taken_on = "2026-09-13"
sku_id   = ""
"""


def test_the_shipped_table_loads():
    table = load_prices(SHIPPED)
    assert table.has("google/machine-type/e2-standard-4/us-central1")


def test_the_shipped_amounts_are_exact_decimals_not_floats():
    table = load_prices(SHIPPED)
    row = table.row("google/machine-type/e2-small/us-central1")
    assert isinstance(row.amount, Decimal)
    assert row.amount == Decimal("0.0168")


def test_every_shipped_row_carries_a_source_and_a_date():
    for row in load_prices(SHIPPED).rows:
        assert row.source.startswith("http")
        assert isinstance(row.taken_on, date)


def test_a_missing_key_is_absent_rather_than_free():
    table = load_prices(SHIPPED)
    assert table.has("google/disk/pd-balanced/us-central1") is False


def test_two_rows_with_one_key_are_refused_by_key(tmp_path):
    with pytest.raises(PriceError) as raised:
        a_table(tmp_path, ROW + ROW)
    assert "google/machine-type/e2-standard-4/us-central1" in str(raised.value)


def test_a_table_mixing_currencies_is_refused(tmp_path):
    other = ROW.replace("e2-standard-4", "n2-standard-4").replace('"USD"', '"EUR"')
    with pytest.raises(PriceError) as raised:
        a_table(tmp_path, ROW + other)
    assert "EUR" in str(raised.value)


def test_the_oldest_row_is_reported_so_staleness_is_visible(tmp_path):
    older = ROW.replace("e2-standard-4", "e2-medium").replace("2026-09-13", "2026-01-04")
    table = a_table(tmp_path, ROW + older)
    assert table.oldest == date(2026, 1, 4)


def test_an_hourly_price_becomes_monthly_at_730_hours(tmp_path):
    table = a_table(tmp_path, ROW)
    unit = Unit(key="google/machine-type/e2-standard-4/us-central1", quantity=Decimal(3))
    assert table.monthly(unit) == Decimal("0.134") * HOURS_PER_MONTH * 3


def test_a_monthly_price_is_taken_as_it_stands(tmp_path):
    disk = ROW.replace("machine-type/e2-standard-4", "disk/pd-balanced")
    disk = disk.replace('unit     = "hour"', 'unit     = "GB-month"').replace("0.134", "0.10")
    table = a_table(tmp_path, disk)
    unit = Unit(key="google/disk/pd-balanced/us-central1", quantity=Decimal(500))
    assert table.monthly(unit) == Decimal("0.10") * 500


def test_pricing_a_unit_with_no_row_is_an_error_not_a_zero(tmp_path):
    table = a_table(tmp_path, ROW)
    with pytest.raises(PriceError):
        table.monthly(Unit(key="google/disk/pd-ssd/us-central1", quantity=Decimal(10)))
