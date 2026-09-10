"""Nothing may be silently dropped. An unpriced resource and unattributed spend
are both findings in their own right, and discarding either understates the bill.
"""

from decimal import Decimal

from cost_agent.inputs import load_inputs

COSTS = """resource_id,cloud,service,tags,period_cost
r-1,gcp,gke,owner=platform,1200.50
r-2,gcp,cloudsql,team=data,800.25
r-orphan-cost,gcp,storage,,42.10
"""

INVENTORY = """[
  {"resource_id": "r-1", "kind": "compute", "utilisation_avg": 0.38, "age_days": 400,
   "attached": true, "commitment_covered": false, "tags": {"owner": "platform"}},
  {"resource_id": "r-2", "kind": "database", "utilisation_avg": 0.55, "age_days": 300,
   "attached": true, "commitment_covered": false, "tags": {"team": "data"}},
  {"resource_id": "r-orphan-inv", "kind": "storage", "age_days": 90,
   "attached": false, "commitment_covered": false, "tags": {}}
]"""


def write_pair(tmp_path):
    costs = tmp_path / "costs.csv"
    inventory = tmp_path / "inventory.json"
    costs.write_text(COSTS)
    inventory.write_text(INVENTORY)
    return costs, inventory


def test_records_present_in_both_inputs_are_joined(tmp_path):
    inputs = load_inputs(*write_pair(tmp_path))

    assert {r.resource_id for r in inputs.matched} == {"r-1", "r-2"}


def test_a_priced_resource_missing_from_the_inventory_survives_as_unmatched(tmp_path):
    inputs = load_inputs(*write_pair(tmp_path))

    orphan = next(u for u in inputs.unmatched if u.resource_id == "r-orphan-cost")
    assert orphan.present_in == "cost_export"
    assert orphan.period_cost == Decimal("42.10")


def test_an_inventoried_resource_missing_from_the_bill_survives_as_unmatched(tmp_path):
    inputs = load_inputs(*write_pair(tmp_path))

    orphan = next(u for u in inputs.unmatched if u.resource_id == "r-orphan-inv")
    assert orphan.present_in == "inventory"
    assert orphan.period_cost is None


def test_money_is_decimal_at_the_boundary_so_no_float_enters_the_arithmetic(tmp_path):
    inputs = load_inputs(*write_pair(tmp_path))

    for resource in inputs.matched:
        assert isinstance(resource.period_cost, Decimal)
    assert inputs.total_period_cost == Decimal("2042.85")


def test_tags_are_parsed_from_the_cost_export(tmp_path):
    inputs = load_inputs(*write_pair(tmp_path))

    resource = next(r for r in inputs.matched if r.resource_id == "r-1")
    assert resource.tags["owner"] == "platform"
