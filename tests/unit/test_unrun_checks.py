"""A rule that never ran is recorded as it fails to run.

Found on a real inventory: no resource carried a `provisioned` figure and a
third carried no utilisation, so three rules evaluated nothing. The report named
none of them, and reported a capacity management driver worth a fifth of the
bill built on the rules that did run. A reader could see the empty sections and
could not see the absent fields.

This is the repository's own principle, that checked and found nothing differs
from never checked, applied to inputs instead of report sections. It matters
more on the inputs, because an empty heading is visible and a missing field is
not.

The gaps come from the classifier rather than from a table of rules and the
fields they need. A table would be a second statement of `_classify_one`'s
branches and would drift from them the first time a rule changed. The condition
that decides a rule cannot run and the record that it did not are the same line.
"""

from datetime import datetime

import pytest

from cost_agent.classify import Rule, classify, classify_with_gaps
from cost_agent.inputs import Inputs


@pytest.fixture
def gaps_for(thresholds, as_of):
    def _gaps(resource):
        _, gaps = classify_with_gaps(
            Inputs((resource,), (), resource.period_cost), thresholds, as_of
        )
        return {(gap.rule, gap.field) for gap in gaps}

    return _gaps


@pytest.fixture
def complete(make_resource):
    """Every optional field supplied. Nothing here can be a gap.

    `kind` is compute, so the capacity and utilisation rules apply to it. The
    tier rules do not, which is what the storage fixture below is for.
    """
    return make_resource(
        "complete",
        "1000.00",
        provisioned=8.0,
        observed_peak=6.0,
        utilisation_avg=0.75,
        weekday_utilisation=0.8,
        weekend_utilisation=0.7,
    )


@pytest.fixture
def bucket(make_resource):
    """Storage, with a tier and a last access. The only kind cold_on_hot_tier
    applies to at all."""
    return make_resource(
        "bucket",
        "1000.00",
        kind="storage",
        utilisation_avg=None,
        tier="standard",
        last_access=datetime(2026, 8, 30),
    )


def test_a_fully_populated_resource_has_no_gaps(gaps_for, complete):
    assert gaps_for(complete) == set()


def test_oversized_gaps_when_provisioned_is_absent(gaps_for, complete):
    import dataclasses

    assert (Rule.OVERSIZED, "provisioned") in gaps_for(
        dataclasses.replace(complete, provisioned=None)
    )


def test_oversized_gaps_when_the_peak_is_absent(gaps_for, complete):
    import dataclasses

    assert (Rule.OVERSIZED, "observed_peak") in gaps_for(
        dataclasses.replace(complete, observed_peak=None)
    )


def test_peak_shaped_gaps_on_either_half_of_the_pair(gaps_for, complete):
    import dataclasses

    weekday = gaps_for(dataclasses.replace(complete, weekday_utilisation=None))
    weekend = gaps_for(dataclasses.replace(complete, weekend_utilisation=None))
    assert (Rule.PEAK_SHAPED_ALWAYS_ON, "weekday_utilisation") in weekday
    assert (Rule.PEAK_SHAPED_ALWAYS_ON, "weekend_utilisation") in weekend


def test_a_bucket_with_everything_it_can_have_produces_no_gaps(gaps_for, bucket):
    """No utilisation, no capacity numbers, and none of that is a gap: a bucket
    has none of those to be missing."""
    assert gaps_for(bucket) == set()


def test_cold_on_hot_tier_gaps_when_the_tier_is_unknown(gaps_for, bucket):
    import dataclasses

    assert (Rule.COLD_ON_HOT_TIER, "tier") in gaps_for(
        dataclasses.replace(bucket, tier=None)
    )


def test_cold_on_hot_tier_gaps_when_a_hot_tier_has_no_last_access(gaps_for, bucket):
    import dataclasses

    assert (Rule.COLD_ON_HOT_TIER, "last_access") in gaps_for(
        dataclasses.replace(bucket, tier="standard", last_access=None)
    )


def test_a_cold_tier_with_no_last_access_is_not_a_gap(gaps_for, bucket):
    """The rule ran and the answer was no. Reporting that as unrun would be the
    same overstatement in the opposite direction from the one this fixes."""
    import dataclasses

    gaps = gaps_for(dataclasses.replace(bucket, tier="nearline", last_access=None))
    assert not any(rule is Rule.COLD_ON_HOT_TIER for rule, _ in gaps)


def test_a_machine_with_no_tier_is_not_a_gap(gaps_for, complete):
    """A virtual machine has no storage class to be missing, and a report full
    of inapplicable checks is the report people learn to skip."""
    gaps = gaps_for(complete)
    assert not any(rule is Rule.COLD_ON_HOT_TIER for rule, _ in gaps)


def test_the_utilisation_rules_gap_together(gaps_for, complete):
    import dataclasses

    gaps = gaps_for(dataclasses.replace(complete, utilisation_avg=None))
    for rule in (Rule.IDLE, Rule.UNDER_UTILISED, Rule.NO_COMMITMENT):
        assert (rule, "utilisation_avg") in gaps


def test_untagged_and_stale_never_gap(gaps_for, complete):
    """Both read fields that are always present, by default or construction."""
    import dataclasses

    gaps = gaps_for(dataclasses.replace(complete, tags={}, attached=False))
    assert not any(
        rule in (Rule.UNTAGGED, Rule.STALE_UNATTACHED) for rule, _ in gaps
    )


def test_the_decommission_rules_never_gap(gaps_for, complete):
    """An absent decommission date means not scheduled, which is a statement
    rather than a gap."""
    import dataclasses

    gaps = gaps_for(dataclasses.replace(complete, decommission_at=None))
    assert not any(
        rule in (Rule.SCHEDULED_DECOMMISSION, Rule.OVERDUE_DECOMMISSION)
        for rule, _ in gaps
    )


def test_classify_returns_exactly_what_it_returned_before(
    thresholds, as_of, complete, make_resource
):
    """The wrapper is what stops this being a breaking change."""
    resources = (complete, make_resource("other", "50.00", utilisation_avg=0.02))
    inputs = Inputs(resources, (), sum(r.period_cost for r in resources))
    findings, _ = classify_with_gaps(inputs, thresholds, as_of)
    assert classify(inputs, thresholds, as_of) == findings


def test_gaps_are_recorded_per_resource(gaps_for, thresholds, as_of, make_resource):
    """Two resources missing the same field are two gaps, not one, or the count
    in the report would be meaningless."""
    resources = tuple(
        make_resource(f"r-{n}", "100.00", utilisation_avg=None) for n in range(3)
    )
    inputs = Inputs(resources, (), sum(r.period_cost for r in resources))
    _, gaps = classify_with_gaps(inputs, thresholds, as_of)
    idle = [gap for gap in gaps if gap.rule is Rule.IDLE]
    assert {gap.resource_id for gap in idle} == {"r-0", "r-1", "r-2"}


def test_an_estate_with_no_resources_produces_no_gaps(thresholds, as_of):
    from decimal import Decimal

    findings, gaps = classify_with_gaps(Inputs((), (), Decimal("0")), thresholds, as_of)
    assert (findings, gaps) == ([], [])
