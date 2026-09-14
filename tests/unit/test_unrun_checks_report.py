"""The report names the checks that could not run.

A rule that ran and found nothing, and a rule that never ran at all, are
different claims. This report already keeps that distinction for its own
sections, which print `none` rather than disappearing. It did not keep it for
its inputs, which is where it matters more: a reader can see an empty heading
and cannot see an absent field.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from cost_agent.classify import classify_with_gaps
from cost_agent.drivers import build_analysis
from cost_agent.inputs import Inputs
from cost_agent.report import render_report

HEADING = "Checks that could not run"


@pytest.fixture
def report_for(thresholds, as_of):
    def _report(resources) -> str:
        total = sum((r.period_cost for r in resources), Decimal("0"))
        inputs = Inputs(tuple(resources), (), total)
        findings, gaps = classify_with_gaps(inputs, thresholds, as_of)
        return render_report(build_analysis(findings, inputs, thresholds, gaps=gaps))

    return _report


@pytest.fixture
def complete(make_resource):
    def _complete(resource_id="complete", **overrides):
        base = dict(
            provisioned=8.0,
            observed_peak=6.0,
            utilisation_avg=0.75,
            weekday_utilisation=0.8,
            weekend_utilisation=0.7,
            tier="standard",
            last_access=datetime(2026, 8, 30),
        )
        return make_resource(resource_id, "1000.00", **{**base, **overrides})

    return _complete


def line_for(report: str, rule: str) -> str:
    return next(ln for ln in report.splitlines() if ln.strip().startswith(f"- {rule}"))


def test_the_section_renders_when_nothing_is_missing(report_for, complete):
    """Like every other section here. An absent heading and "nothing missing"
    are different claims."""
    report = report_for([complete()])
    assert HEADING in report
    assert "none." in report.split(HEADING)[1]


def test_a_rule_with_complete_data_is_not_named(report_for, complete):
    assert "oversized" not in report_for([complete()])


def test_a_rule_that_could_not_run_is_named_with_its_field(report_for, complete):
    report = report_for([complete(provisioned=None)])
    assert "provisioned" in line_for(report, "oversized")


def test_it_counts_resources_not_gaps(report_for, complete):
    """Three resources missing one field is three, not three times the number
    of rules that field stopped."""
    report = report_for([complete(f"r-{n}", utilisation_avg=None) for n in range(3)])
    assert "3 of 3" in line_for(report, "idle")


def test_a_field_absent_on_some_resources_says_so(report_for, complete):
    resources = [complete("a", provisioned=None), complete("b"), complete("c")]
    assert "1 of 3" in line_for(report_for(resources), "oversized")


def test_a_rule_missing_different_fields_on_different_resources_names_both(
    report_for, complete
):
    resources = [complete("a", provisioned=None), complete("b", observed_peak=None)]
    line = line_for(report_for(resources), "oversized")
    assert "provisioned" in line
    assert "observed_peak" in line


def test_one_absent_field_names_every_rule_it_stopped(report_for, complete):
    """"idle could not run" is what a reader needs, not "a field was missing"."""
    report = report_for([complete(utilisation_avg=None)])
    for rule in ("idle", "under_utilised", "no_commitment"):
        assert line_for(report, rule)


def test_a_cold_tier_is_not_reported_as_unrun(report_for, make_resource):
    """The rule ran and the answer was no."""
    bucket = make_resource(
        "b", "1000.00", kind="storage", utilisation_avg=None, tier="nearline"
    )
    assert "cold_on_hot_tier" not in report_for([bucket])


def test_a_storage_resource_is_not_reported_as_missing_capacity_numbers(
    report_for, make_resource
):
    """A bucket has no provisioned size or weekday utilisation to be missing,
    and a report full of inapplicable checks is the report people skip."""
    bucket = make_resource(
        "b",
        "1000.00",
        kind="storage",
        utilisation_avg=None,
        tier="nearline",
        tags={"owner": "platform"},
    )
    report = report_for([bucket])
    assert "none." in report.split(HEADING)[1]


def test_an_empty_estate_renders_the_section_and_claims_nothing(report_for):
    report = report_for([])
    assert HEADING in report
    assert "none." in report.split(HEADING)[1]


def test_the_rules_come_out_in_a_stable_order(report_for, complete):
    """The same estate must produce the same report twice."""
    resources = [complete(provisioned=None, utilisation_avg=None, tier=None)]
    assert report_for(resources) == report_for(resources)


def test_it_changes_no_verdict(report_for, complete):
    """The section is a statement to a reader. The analysis above it is what it
    was before."""
    with_gap = report_for([complete("a", provisioned=None)])
    assert "COST DRIVER ANALYSIS" in with_gap
    assert "Attributed to drivers" in with_gap
