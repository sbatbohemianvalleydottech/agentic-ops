"""Classification reads thresholds and observable properties. Never service names.

That constraint is the difference between a tool that analyses an estate and one
that recognises the fixture it was built against, so it is asserted rather than
intended.
"""

from datetime import datetime
from decimal import Decimal

from cost_agent.classify import Rule, classify
from cost_agent.inputs import Inputs, Resource
from cost_agent.thresholds import load_thresholds

THRESHOLDS = load_thresholds()
AS_OF = datetime(2026, 9, 1)


def resource(**overrides) -> Resource:
    base = dict(
        resource_id="r-1",
        cloud="gcp",
        service="kubernetes",
        period_cost=Decimal("1000.00"),
        kind="compute",
        tags={"owner": "platform"},
        utilisation_avg=0.75,
        age_days=100,
        attached=True,
        commitment_covered=True,
    )
    return Resource(**{**base, **overrides})


def rules_for(res: Resource) -> set[Rule]:
    findings = classify(Inputs((res,), (), res.period_cost), THRESHOLDS, AS_OF)
    return {finding.rule for finding in findings}


def test_a_healthy_resource_produces_no_findings():
    assert rules_for(resource()) == set()


def test_idle_fires_at_the_ceiling_and_not_above_it():
    assert Rule.IDLE in rules_for(resource(utilisation_avg=THRESHOLDS.idle_ceiling))
    assert Rule.IDLE not in rules_for(
        resource(utilisation_avg=THRESHOLDS.idle_ceiling + 0.01)
    )


def test_under_utilised_fires_below_the_target_floor_but_not_at_it():
    assert Rule.UNDER_UTILISED in rules_for(
        resource(utilisation_avg=THRESHOLDS.target_floor - 0.01)
    )
    assert Rule.UNDER_UTILISED not in rules_for(
        resource(utilisation_avg=THRESHOLDS.target_floor)
    )


def test_oversized_fires_on_the_provisioned_to_peak_ratio():
    assert Rule.OVERSIZED in rules_for(resource(provisioned=100, observed_peak=50))
    assert Rule.OVERSIZED not in rules_for(resource(provisioned=100, observed_peak=90))


def test_a_peak_shaped_fleet_is_caught_by_the_weekday_to_weekend_ratio():
    assert Rule.PEAK_SHAPED_ALWAYS_ON in rules_for(
        resource(weekday_utilisation=0.70, weekend_utilisation=0.05)
    )
    assert Rule.PEAK_SHAPED_ALWAYS_ON not in rules_for(
        resource(weekday_utilisation=0.70, weekend_utilisation=0.60)
    )


def test_cold_data_on_a_hot_tier_is_caught_relative_to_the_analysis_date():
    cold = resource(
        kind="storage", tier="standard", last_access=datetime(2026, 1, 1),
        utilisation_avg=None,
    )
    warm = resource(
        kind="storage", tier="standard", last_access=datetime(2026, 8, 25),
        utilisation_avg=None,
    )

    assert Rule.COLD_ON_HOT_TIER in rules_for(cold)
    assert Rule.COLD_ON_HOT_TIER not in rules_for(warm)


def test_already_tiered_storage_is_not_flagged_as_cold():
    assert Rule.COLD_ON_HOT_TIER not in rules_for(
        resource(kind="storage", tier="coldline", last_access=datetime(2026, 1, 1),
                 utilisation_avg=None)
    )


def test_an_unattached_volume_past_the_stale_window_is_caught():
    assert Rule.STALE_UNATTACHED in rules_for(
        resource(kind="storage", attached=False, age_days=200, utilisation_avg=None)
    )
    assert Rule.STALE_UNATTACHED not in rules_for(
        resource(kind="storage", attached=False, age_days=3, utilisation_avg=None)
    )


def test_steady_uncommitted_usage_is_a_commercial_finding():
    assert Rule.NO_COMMITMENT in rules_for(
        resource(utilisation_avg=0.80, commitment_covered=False)
    )


def test_lightly_used_capacity_is_not_a_commitment_candidate():
    """Committing to capacity you should be shrinking would lock in the waste."""
    assert Rule.NO_COMMITMENT not in rules_for(
        resource(utilisation_avg=0.20, commitment_covered=False)
    )


def test_a_resource_with_no_owner_tag_is_flagged():
    assert Rule.UNTAGGED in rules_for(resource(tags={}))
    assert Rule.UNTAGGED not in rules_for(resource(tags={"cost_centre": "eng"}))


def test_missing_utilisation_is_unassessable_and_never_healthy():
    rules = rules_for(resource(kind="compute", utilisation_avg=None))

    assert Rule.UNASSESSABLE in rules
    assert Rule.UNDER_UTILISED not in rules
    assert Rule.IDLE not in rules


def test_the_same_shape_classifies_identically_whatever_the_service_is_called():
    """If renaming the service changes the finding, the tool is pattern-matching
    on a fixture rather than analysing an estate."""
    shape = dict(utilisation_avg=0.30, provisioned=100, observed_peak=40)

    assert rules_for(resource(service="kubernetes", cloud="gcp", **shape)) == rules_for(
        resource(service="some-service-nobody-has-heard-of", cloud="aws", **shape)
    )


def test_a_finding_carries_the_values_that_made_its_rule_fire():
    """Principle II: the evidence travels with the claim."""
    findings = classify(
        Inputs((resource(utilisation_avg=0.30),), (), Decimal("1000.00")),
        THRESHOLDS,
        AS_OF,
    )

    finding = next(f for f in findings if f.rule is Rule.UNDER_UTILISED)
    assert "utilisation_avg" in finding.observed
    assert finding.observed["utilisation_avg"] == 0.30
