"""Attribution. Every dollar belongs to exactly one driver.

An analysis whose drivers sum to more than the bill is dismissed on sight, so
the totals are asserted exactly rather than within a tolerance.
"""

from decimal import Decimal

import pytest

from cost_agent.classify import RootCause, classify
from cost_agent.drivers import build_analysis
from cost_agent.inputs import Inputs, Unmatched


@pytest.fixture
def analyse(thresholds, as_of):
    def _analyse(resources, unmatched=()):
        total = sum((r.period_cost for r in resources), Decimal("0"))
        inputs = Inputs(tuple(resources), tuple(unmatched), total)
        return build_analysis(classify(inputs, thresholds, as_of), inputs, thresholds)

    return _analyse


def driver_for(analysis, root_cause):
    return next((d for d in analysis.drivers if d.root_cause is root_cause), None)


def stale_and_idle(make_resource, resource_id="r-both", cost="1000.00"):
    """Matches workload elimination and capacity management at once."""
    return make_resource(
        resource_id, cost, kind="storage", tier="standard",
        attached=False, age_days=300, utilisation_avg=0.10,
    )


def test_a_resource_matching_several_root_causes_goes_to_the_highest(
    analyse, make_resource
):
    """Stale and unattached beats under-utilised. There is no point right-sizing
    something you are about to delete."""
    analysis = analyse([
        stale_and_idle(make_resource),
        make_resource("r-other", "500.00", utilisation_avg=0.20),
    ])

    elimination = driver_for(analysis, RootCause.WORKLOAD_ELIMINATION)
    capacity = driver_for(analysis, RootCause.CAPACITY_MANAGEMENT)
    assert "r-both" in {f.resource_id for f in elimination.findings}
    assert "r-both" not in {f.resource_id for f in capacity.findings}


def test_a_contested_resource_records_what_it_beat_and_why(analyse, make_resource):
    analysis = analyse([stale_and_idle(make_resource)])

    contest = next(c for c in analysis.contested if c.resource_id == "r-both")
    assert contest.assigned_to is RootCause.WORKLOAD_ELIMINATION
    assert RootCause.CAPACITY_MANAGEMENT in contest.also_matched
    assert contest.basis


def test_driver_totals_never_exceed_the_bill(analyse, make_resource):
    analysis = analyse([
        make_resource("r-1", "1000.00", utilisation_avg=0.10),
        make_resource("r-2", "2000.00", kind="storage", tier="standard",
                      attached=False, age_days=300, utilisation_avg=None),
        make_resource("r-3", "3000.00", utilisation_avg=0.80, commitment_covered=False),
        make_resource("r-4", "4000.00"),
    ])

    assert sum((d.annual_cost for d in analysis.drivers), Decimal("0")) <= (
        analysis.total_bill_annual
    )


def test_every_resource_is_accounted_for_exactly_once(analyse, make_resource):
    analysis = analyse(
        [
            make_resource("r-attributed", "1000.00", utilisation_avg=0.10),
            make_resource("r-unassessable", "500.00", utilisation_avg=None),
            make_resource("r-healthy", "700.00"),
        ],
        [Unmatched("r-unmatched", "cost_export", Decimal("42.00"))],
    )

    seen = (
        [f.resource_id for d in analysis.drivers for f in d.findings]
        + [f.resource_id for f in analysis.unassessable]
        + [u.resource_id for u in analysis.unmatched]
        + list(analysis.healthy)
    )
    assert sorted(seen) == sorted(
        ["r-attributed", "r-unassessable", "r-healthy", "r-unmatched"]
    )


def test_a_driver_explaining_one_resource_is_flagged(analyse, make_resource):
    """A driver that explains one line is a line item wearing a better name."""
    analysis = analyse([
        make_resource("r-alone", "1000.00", kind="storage", tier="standard",
                      attached=False, age_days=300, utilisation_avg=None),
        make_resource("r-a", "500.00", utilisation_avg=0.20),
        make_resource("r-b", "500.00", utilisation_avg=0.25),
    ])

    assert driver_for(analysis, RootCause.WORKLOAD_ELIMINATION).single_resource is True
    assert driver_for(analysis, RootCause.CAPACITY_MANAGEMENT).single_resource is False


def test_annualisation_uses_the_configured_multiplier_and_reports_it(
    analyse, make_resource, thresholds
):
    analysis = analyse([make_resource("r-1", "1000.00", utilisation_avg=0.10)])

    assert analysis.annualisation_multiplier == thresholds.annualisation_multiplier
    assert analysis.total_bill_annual == (
        Decimal("1000.00") * thresholds.annualisation_multiplier
    ).quantize(Decimal("0.01"))


def test_a_driver_names_an_absent_practice_not_a_condition(analyse, make_resource):
    """Not 'poor utilisation' but the management practice that is missing."""
    analysis = analyse([
        make_resource("r-a", "500.00", utilisation_avg=0.20),
        make_resource("r-b", "500.00", utilisation_avg=0.25),
    ])

    assert driver_for(analysis, RootCause.CAPACITY_MANAGEMENT).absent_practice


def test_drivers_are_ordered_by_cost_descending(analyse, make_resource):
    analysis = analyse([
        make_resource("r-small", "100.00", kind="storage", tier="standard",
                      attached=False, age_days=300, utilisation_avg=None),
        make_resource("r-big-a", "5000.00", utilisation_avg=0.20),
        make_resource("r-big-b", "5000.00", utilisation_avg=0.25),
    ])

    costs = [d.annual_cost for d in analysis.drivers]
    assert costs == sorted(costs, reverse=True)
