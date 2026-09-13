"""Turning changes into a monthly figure.

A deletion is a credit and a replacement is a difference. Getting either wrong
overstates the cost of exactly the changes careful teams write: swapping a
machine type, or removing something.
"""

from decimal import Decimal
from pathlib import Path

from test_plan_parse import a_change, a_plan

from plan_cost.plan import parse_plan
from plan_cost.prices import load_prices
from plan_cost.pricing import price_plan

SHIPPED = Path(__file__).resolve().parents[2] / "plan_cost" / "prices.toml"
E2_STANDARD_4_MONTH = Decimal("0.134") * 730
E2_SMALL_MONTH = Decimal("0.0168") * 730


def priced(*raw):
    return price_plan(parse_plan(a_plan(list(raw))).changes, load_prices(SHIPPED))


def node_pool(actions, *, machine="e2-standard-4", count=3, state="after"):
    attributes = {
        "location": "us-central1",
        "node_count": count,
        "node_config": [{"machine_type": machine}],
    }
    return a_change(
        actions,
        address="google_container_node_pool.primary",
        type="google_container_node_pool",
        **{state: attributes},
    )


def test_a_creation_costs_its_full_monthly_price():
    result = priced(node_pool(["create"]))
    assert result.total == E2_STANDARD_4_MONTH * 3


def test_a_deletion_is_a_credit():
    result = priced(node_pool(["delete"], state="before"))
    assert result.total == -E2_STANDARD_4_MONTH * 3


def test_an_update_is_the_difference_not_the_new_price():
    change = a_change(
        ["update"],
        type="google_container_node_pool",
        before={"location": "us-central1", "node_count": 3,
                "node_config": [{"machine_type": "e2-small"}]},
        after={"location": "us-central1", "node_count": 3,
               "node_config": [{"machine_type": "e2-standard-4"}]},
    )
    result = priced(change)
    assert result.total == (E2_STANDARD_4_MONTH - E2_SMALL_MONTH) * 3


def test_both_replacement_orders_are_priced_as_a_difference():
    def replacement(actions):
        return a_change(
            actions,
            type="google_compute_instance",
            before={"zone": "us-central1-a", "machine_type": "e2-standard-4"},
            after={"zone": "us-central1-a", "machine_type": "e2-small"},
        )

    destroy_first = priced(replacement(["delete", "create"])).total
    create_first = priced(replacement(["create", "delete"])).total
    assert destroy_first == create_first == E2_SMALL_MONTH - E2_STANDARD_4_MONTH


def test_a_total_is_the_sum_of_its_lines():
    result = priced(
        node_pool(["create"]),
        a_change(["create"], type="google_compute_instance",
                 after={"zone": "us-central1-a", "machine_type": "e2-small"}),
    )
    assert result.total == sum(line.delta for line in result.lines)
    assert len(result.lines) == 2


def test_autoscaled_capacity_is_priced_at_its_floor_and_says_so():
    change = a_change(
        ["create"],
        type="google_container_node_pool",
        after={
            "location": "us-central1",
            "autoscaling": [{"min_node_count": 2, "max_node_count": 10}],
            "node_config": [{"machine_type": "e2-standard-4"}],
        },
    )
    line = priced(change).lines[0]
    assert line.delta == E2_STANDARD_4_MONTH * 2
    assert line.at_minimum is True


def test_resources_that_could_not_be_priced_are_not_in_the_total():
    result = priced(
        node_pool(["create"]),
        a_change(["create"], type="google_storage_bucket", after={"location": "US"}),
        a_change(["create"], type="google_compute_disk",
                 after={"zone": "us-central1-a", "type": "pd-balanced", "size": 500}),
    )
    assert result.total == E2_STANDARD_4_MONTH * 3
    assert len(result.lines) == 1
    assert sum(result.coverage.counts.values()) == 3


def test_a_plan_where_nothing_is_priceable_claims_no_figure():
    result = priced(
        a_change(["create"], type="incident_io_team", provider="incident-io/incident"),
        a_change(["create"], type="datadog_monitor", provider="DataDog/datadog"),
    )
    assert result.lines == []
    assert result.has_figure is False


def test_no_change_actions_contribute_nothing():
    result = priced(a_change(["no-op"]), a_change(["read"]))
    assert result.total == 0
    assert result.has_figure is False
