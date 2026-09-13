"""Refreshing prices from the vendor's own catalogue.

The point of this is that no figure in the table was typed by a person. The
point of the reporting around it is that a row nobody could refresh must never
end up looking fresh, which is the failure a refresher invites.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from plan_cost.prices import load_prices
from plan_cost.refresh import refresh_prices

CATALOGUE = (
    Path(__file__).resolve().parents[2] / "plan_cost" / "fixtures" / "catalogue" / "skus.json"
)

TABLE = """# A table with a comment that must survive.

[[price]]
key      = "google/machine-type/e2-standard-4/us-central1"
unit     = "hour"
amount   = "0.134"
currency = "USD"
region   = "us-central1"
source   = "https://gcloud-compute.com/e2-standard-4.html"
taken_on = "2026-01-04"
sku_id   = ""

# A comment between rows, which must also survive.

[[price]]
key      = "google/disk/pd-balanced/us-central1"
unit     = "GB-month"
amount   = "0.09"
currency = "USD"
region   = "us-central1"
source   = "https://example.test/old"
taken_on = "2026-01-04"
sku_id   = ""

[[map]]
key         = "google/disk/pd-balanced/us-central1"
unit        = "GB-month"
region      = "us-central1"
description = "Balanced PD Capacity"

[[map]]
key         = "google/disk/pd-extreme/us-central1"
unit        = "GB-month"
region      = "us-central1"
description = "Extreme PD Capacity"
"""


def catalogue():
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


def a_table(tmp_path, body=TABLE):
    path = tmp_path / "prices.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_mapped_row_takes_its_amount_from_the_catalogue(tmp_path):
    path = a_table(tmp_path)
    report = refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    row = load_prices(path).row("google/disk/pd-balanced/us-central1")
    assert row.amount == Decimal("0.10")
    assert "google/disk/pd-balanced/us-central1" in report.updated


def test_a_refreshed_row_records_the_vendor_identifier_and_the_date(tmp_path):
    path = a_table(tmp_path)
    refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    row = load_prices(path).row("google/disk/pd-balanced/us-central1")
    assert row.sku_id == "D973-5D65-BAB2"
    assert row.taken_on == date(2026, 9, 13)
    assert "cloudbilling.googleapis.com" in row.source


def test_units_and_nanos_become_one_decimal(tmp_path):
    """0 units and 100000000 nanos is ten cents, not a rounding of it."""
    path = a_table(tmp_path)
    refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    assert load_prices(path).row("google/disk/pd-balanced/us-central1").amount == Decimal("0.10")


def test_a_mapping_that_matches_nothing_is_reported_and_writes_nothing(tmp_path):
    path = a_table(tmp_path)
    report = refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    assert "google/disk/pd-extreme/us-central1" in dict(report.unmatched)
    assert load_prices(path).has("google/disk/pd-extreme/us-central1") is False


def test_a_row_nobody_can_refresh_is_named_and_left_exactly_as_it_was(tmp_path):
    """Machine types have no single SKU, because cores and memory are priced
    separately, so those rows must not come out of a refresh looking fresh."""
    path = a_table(tmp_path)
    before = path.read_text(encoding="utf-8")
    report = refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    after = path.read_text(encoding="utf-8")

    assert "google/machine-type/e2-standard-4/us-central1" in report.unrefreshable
    machine_block = [line for line in after.splitlines() if "e2-standard-4" in line]
    assert machine_block == [line for line in before.splitlines() if "e2-standard-4" in line]
    assert load_prices(path).row(
        "google/machine-type/e2-standard-4/us-central1"
    ).taken_on == date(2026, 1, 4)


def test_the_comments_survive_a_refresh(tmp_path):
    path = a_table(tmp_path)
    refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    text = path.read_text(encoding="utf-8")
    assert "# A table with a comment that must survive." in text
    assert "# A comment between rows, which must also survive." in text


def test_a_mapping_with_no_row_yet_adds_one(tmp_path):
    body = TABLE.replace(
        """[[price]]
key      = "google/disk/pd-balanced/us-central1"
unit     = "GB-month"
amount   = "0.09"
currency = "USD"
region   = "us-central1"
source   = "https://example.test/old"
taken_on = "2026-01-04"
sku_id   = ""
""",
        "",
    )
    path = a_table(tmp_path, body)
    report = refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    assert "google/disk/pd-balanced/us-central1" in report.added
    assert load_prices(path).row("google/disk/pd-balanced/us-central1").amount == Decimal("0.10")


def test_a_sku_priced_in_tiers_is_refused_rather_than_flattened(tmp_path):
    """Egress is cheaper above ten terabytes. Picking one of those numbers and
    calling it the price would be a choice the table could not show."""
    body = TABLE + """
[[map]]
key         = "google/network/internet-egress/us-central1"
unit        = "GB-month"
region      = "us-central1"
description = "Network Internet Egress from Americas to Americas"
"""
    path = a_table(tmp_path, body)
    report = refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    reason = dict(report.unmatched)["google/network/internet-egress/us-central1"]
    assert "tier" in reason


def test_a_sku_in_another_region_does_not_match(tmp_path):
    body = TABLE.replace('region      = "us-central1"\ndescription = "Balanced PD Capacity"',
                         'region      = "europe-west1"\ndescription = "Balanced PD Capacity"')
    path = a_table(tmp_path, body)
    report = refresh_prices(path, catalogue(), today=date(2026, 9, 13))
    assert any("europe-west1" in key for key, _ in report.unmatched) or report.unmatched
