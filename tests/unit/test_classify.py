"""Classification reads thresholds and observable properties. Never service names.

That constraint is the difference between a tool that analyses an estate and one
that recognises the fixture it was built against, so it is asserted rather than
intended.
"""

from datetime import datetime

import pytest

from cost_agent.classify import Rule, classify
from cost_agent.inputs import Inputs


@pytest.fixture
def rules_for(thresholds, as_of):
    """Classify one resource and return just the rules that fired."""

    def _rules(resource) -> set[Rule]:
        findings = classify(
            Inputs((resource,), (), resource.period_cost), thresholds, as_of
        )
        return {finding.rule for finding in findings}

    return _rules


def test_a_healthy_resource_produces_no_findings(rules_for, make_resource):
    assert rules_for(make_resource()) == set()


def test_idle_fires_at_the_ceiling_and_not_above_it(
    rules_for, make_resource, thresholds
):
    assert Rule.IDLE in rules_for(
        make_resource(utilisation_avg=thresholds.idle_ceiling)
    )
    assert Rule.IDLE not in rules_for(
        make_resource(utilisation_avg=thresholds.idle_ceiling + 0.01)
    )


def test_under_utilised_fires_below_the_target_floor_but_not_at_it(
    rules_for, make_resource, thresholds
):
    assert Rule.UNDER_UTILISED in rules_for(
        make_resource(utilisation_avg=thresholds.target_floor - 0.01)
    )
    assert Rule.UNDER_UTILISED not in rules_for(
        make_resource(utilisation_avg=thresholds.target_floor)
    )


def test_oversized_fires_on_the_provisioned_to_peak_ratio(rules_for, make_resource):
    assert Rule.OVERSIZED in rules_for(
        make_resource(provisioned=100, observed_peak=50)
    )
    assert Rule.OVERSIZED not in rules_for(
        make_resource(provisioned=100, observed_peak=90)
    )


def test_a_peak_shaped_fleet_is_caught_by_the_weekday_to_weekend_ratio(
    rules_for, make_resource
):
    assert Rule.PEAK_SHAPED_ALWAYS_ON in rules_for(
        make_resource(weekday_utilisation=0.70, weekend_utilisation=0.05)
    )
    assert Rule.PEAK_SHAPED_ALWAYS_ON not in rules_for(
        make_resource(weekday_utilisation=0.70, weekend_utilisation=0.60)
    )


def test_cold_data_on_a_hot_tier_is_caught_relative_to_the_analysis_date(
    rules_for, make_resource
):
    def bucket(last_access):
        return make_resource(
            kind="storage", tier="standard", last_access=last_access,
            utilisation_avg=None,
        )

    assert Rule.COLD_ON_HOT_TIER in rules_for(bucket(datetime(2026, 1, 1)))
    assert Rule.COLD_ON_HOT_TIER not in rules_for(bucket(datetime(2026, 8, 25)))


def test_already_tiered_storage_is_not_flagged_as_cold(rules_for, make_resource):
    assert Rule.COLD_ON_HOT_TIER not in rules_for(
        make_resource(kind="storage", tier="coldline",
                      last_access=datetime(2026, 1, 1), utilisation_avg=None)
    )


def test_an_unattached_volume_past_the_stale_window_is_caught(
    rules_for, make_resource
):
    def volume(age_days):
        return make_resource(
            kind="storage", attached=False, age_days=age_days, utilisation_avg=None
        )

    assert Rule.STALE_UNATTACHED in rules_for(volume(200))
    assert Rule.STALE_UNATTACHED not in rules_for(volume(3))


def test_steady_uncommitted_usage_is_a_commercial_finding(rules_for, make_resource):
    assert Rule.NO_COMMITMENT in rules_for(
        make_resource(utilisation_avg=0.80, commitment_covered=False)
    )


def test_lightly_used_capacity_is_not_a_commitment_candidate(
    rules_for, make_resource
):
    """Committing to capacity you should be shrinking would lock in the waste."""
    assert Rule.NO_COMMITMENT not in rules_for(
        make_resource(utilisation_avg=0.20, commitment_covered=False)
    )


def test_a_resource_with_no_owner_tag_is_flagged(rules_for, make_resource):
    assert Rule.UNTAGGED in rules_for(make_resource(tags={}))
    assert Rule.UNTAGGED not in rules_for(make_resource(tags={"cost_centre": "eng"}))


def test_missing_utilisation_is_unassessable_and_never_healthy(
    rules_for, make_resource
):
    rules = rules_for(make_resource(kind="compute", utilisation_avg=None))

    assert Rule.UNASSESSABLE in rules
    assert Rule.UNDER_UTILISED not in rules
    assert Rule.IDLE not in rules


def test_the_same_shape_classifies_identically_whatever_the_service_is_called(
    rules_for, make_resource
):
    """If renaming the service changes the finding, the tool is pattern-matching
    on a fixture rather than analysing an estate."""
    shape = dict(utilisation_avg=0.30, provisioned=100, observed_peak=40)

    assert rules_for(
        make_resource(service="kubernetes", cloud="gcp", **shape)
    ) == rules_for(
        make_resource(service="some-service-nobody-has-heard-of", cloud="aws", **shape)
    )


def test_a_finding_carries_the_values_that_made_its_rule_fire(
    make_resource, thresholds, as_of
):
    """Principle II: the evidence travels with the claim."""
    resource = make_resource(utilisation_avg=0.30)
    findings = classify(
        Inputs((resource,), (), resource.period_cost), thresholds, as_of
    )

    finding = next(f for f in findings if f.rule is Rule.UNDER_UTILISED)
    assert finding.observed["utilisation_avg"] == 0.30
