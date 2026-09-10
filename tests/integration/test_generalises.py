"""The proof that this analyses an estate rather than recognising a fixture.

If both estates produced the same drivers, the tool would have learned its test
data and the whole exercise would prove nothing.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cost_agent.classify import RootCause
from cost_agent.pipeline import analyse

FIXTURES = Path(__file__).resolve().parents[2] / "cost_agent" / "fixtures"
AS_OF = datetime(2026, 9, 1)


@pytest.fixture(scope="module")
def estate_a():
    return analyse(
        FIXTURES / "estate_a" / "costs.csv",
        FIXTURES / "estate_a" / "inventory.json",
        as_of=AS_OF,
    )


@pytest.fixture(scope="module")
def estate_b():
    return analyse(
        FIXTURES / "estate_b" / "costs.csv",
        FIXTURES / "estate_b" / "inventory.json",
        as_of=AS_OF,
    )


def test_both_estates_produce_drivers(estate_a, estate_b):
    assert estate_a.drivers
    assert estate_b.drivers


def test_the_dominant_driver_differs_between_estates(estate_a, estate_b):
    """A is provisioned for peak and never revisited. B is well-sized but
    uncommitted and littered with detached volumes. Different diseases."""
    assert estate_a.drivers[0].root_cause is not estate_b.drivers[0].root_cause


def test_estate_a_is_dominated_by_capacity_management(estate_a):
    assert estate_a.drivers[0].root_cause is RootCause.CAPACITY_MANAGEMENT


def test_estate_b_is_not_a_capacity_problem(estate_b):
    """Everything in B runs above the target floor. Calling it under-utilised
    would be the tool pattern-matching rather than measuring."""
    capacity = next(
        (d for d in estate_b.drivers if d.root_cause is RootCause.CAPACITY_MANAGEMENT),
        None,
    )
    assert capacity is None or capacity.annual_cost < estate_b.drivers[0].annual_cost


@pytest.mark.parametrize("estate", ["estate_a", "estate_b"])
def test_driver_totals_never_exceed_the_bill_on_either_estate(estate, request):
    analysis = request.getfixturevalue(estate)

    attributed = sum((d.annual_cost for d in analysis.drivers), Decimal("0"))
    assert attributed <= analysis.total_bill_annual


@pytest.mark.parametrize("estate", ["estate_a", "estate_b"])
def test_nothing_is_silently_dropped_on_either_estate(estate, request):
    analysis = request.getfixturevalue(estate)

    accounted = (
        {f.resource_id for d in analysis.drivers for f in d.findings}
        | {f.resource_id for f in analysis.unassessable}
        | {u.resource_id for u in analysis.unmatched}
        | set(analysis.healthy)
    )
    assert len(accounted) == analysis.resource_count


def test_estate_a_reports_the_unassessable_resource(estate_a):
    """a-mystery-1 has no utilisation figure. It must not pass as healthy."""
    assert "a-mystery-1" in {f.resource_id for f in estate_a.unassessable}


def test_estate_a_reports_both_unmatched_resources(estate_a):
    assert {u.resource_id for u in estate_a.unmatched} == {
        "a-orphan-cost",
        "a-orphan-inv",
    }
