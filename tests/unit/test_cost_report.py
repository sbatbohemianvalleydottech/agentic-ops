"""The report is what a reviewer actually reads, so what it omits matters as much
as what it says. Empty sections render as empty rather than disappearing, because
"checked, found nothing" and "never checked" are different claims.
"""

from dataclasses import replace
from decimal import Decimal

import pytest

from cost_agent.classify import classify
from cost_agent.drivers import build_analysis
from cost_agent.inputs import Inputs, Unmatched
from cost_agent.report import render_confidence_reasoning, render_report
from cost_agent.savings import estimate_savings
from ensemble.types import RaterVerdict


@pytest.fixture
def report_for(thresholds, as_of):
    def _report(resources, unmatched=()) -> str:
        total = sum((r.period_cost for r in resources), Decimal("0"))
        inputs = Inputs(tuple(resources), tuple(unmatched), total)
        analysis = build_analysis(classify(inputs, thresholds, as_of), inputs, thresholds)

        annual = {
            r.resource_id: r.period_cost * thresholds.annualisation_multiplier
            for r in resources
        }
        analysis = replace(
            analysis,
            drivers=tuple(
                estimate_savings(d, annual, thresholds) for d in analysis.drivers
            ),
        )
        return render_report(analysis)

    return _report


def two_underused(make_resource):
    return [
        make_resource("r-a", "5000.00", utilisation_avg=0.20),
        make_resource("r-b", "4000.00", utilisation_avg=0.25),
    ]


def test_every_driver_renders_all_seven_required_fields(report_for, make_resource):
    report = report_for(two_underused(make_resource))

    for label in (
        "Cloud", "Annual cost", "Share of bill", "Root cause",
        "Savings", "Confidence", "What would change",
        "Question needed to confirm",
    ):
        assert label in report, f"{label} missing from the driver block"


def test_a_contested_resource_names_the_winner_the_alternative_and_the_basis(
    report_for, make_resource
):
    report = report_for([
        make_resource("r-both", "1000.00", kind="storage", tier="standard",
                      attached=False, age_days=300, utilisation_avg=0.10),
        make_resource("r-other", "500.00", utilisation_avg=0.20),
    ])

    assert "r-both" in report
    assert "WORKLOAD_ELIMINATION" in report
    assert "CAPACITY_MANAGEMENT" in report
    assert "outranks" in report


def test_the_contested_section_is_present_and_empty_when_nothing_overlaps(
    report_for, make_resource
):
    """A reader has to be able to tell 'checked, none found' from 'not checked'."""
    report = report_for(two_underused(make_resource))

    assert "Contested attributions" in report
    assert "none" in report.lower()


def test_unassessable_and_unmatched_sections_render_even_when_empty(
    report_for, make_resource
):
    report = report_for([make_resource("r-a", "5000.00", utilisation_avg=0.20)])

    assert "Unassessable" in report
    assert "Unmatched" in report


def test_unmatched_resources_appear_with_which_side_they_came_from(
    report_for, make_resource
):
    report = report_for(
        [make_resource("r-a", "5000.00", utilisation_avg=0.20)],
        [Unmatched("r-ghost", "cost_export", Decimal("42.00"))],
    )

    assert "r-ghost" in report
    assert "cost_export" in report


def test_the_annualisation_multiplier_is_stated_alongside_the_figure(
    report_for, make_resource, thresholds
):
    """365/30 versus 12 moves the headline by 1.4%. Stating it removes an argument."""
    report = report_for([make_resource("r-a", "5000.00", utilisation_avg=0.20)])

    assert str(thresholds.annualisation_multiplier) in report


def test_the_decommission_horizon_is_stated_with_the_savings(report_for, make_resource):
    """Stops the figure being quoted without the date it depends on."""
    from datetime import datetime

    report = report_for([
        make_resource("r-legacy-a", "5000.00", utilisation_avg=0.38,
                      decommission_at=datetime(2028, 12, 31)),
        make_resource("r-legacy-b", "4000.00", utilisation_avg=0.40,
                      decommission_at=datetime(2027, 6, 30)),
    ])

    assert "2028-12-31" in report
    assert "realised at" in report.lower() or "horizon" in report.lower()


def test_no_horizon_is_claimed_when_nothing_is_scheduled(report_for, make_resource):
    report = report_for(two_underused(make_resource))

    assert "2028" not in report


def test_a_single_resource_driver_is_flagged_in_the_output(report_for, make_resource):
    report = report_for([
        make_resource("r-alone", "1000.00", kind="storage", tier="standard",
                      attached=False, age_days=300, utilisation_avg=None),
        *two_underused(make_resource),
    ])

    assert "one resource" in report.lower()


def test_a_rated_driver_shows_the_reasoning_behind_its_confidence():
    """Same defect as the RCA agent's: the rating was printed and the paid-for
    explanation behind it was dropped before it reached a report at all."""
    verdicts = (
        RaterVerdict(
            rater="anthropic/claude-opus-5",
            grade="high",
            reasoning="Both resources are steady-state, so the utilisation figure "
            "is not an artefact of a sampling window.",
        ),
        RaterVerdict(
            rater="gemini/gemini-3.8-flash",
            grade="high",
            reasoning="No reserved-capacity commitment is recorded against either.",
        ),
    )

    rendered = "\n".join(render_confidence_reasoning(verdicts))

    assert "anthropic/claude-opus-5" in rendered
    assert "gemini/gemini-3.8-flash" in rendered
    assert "steady-state" in rendered
    assert "reserved-capacity commitment" in rendered


def test_two_raters_agreeing_keep_their_separate_reasons():
    """Both said high. They did not say it for the same reason, and merging the
    strings is what destroyed that distinction in the first place."""
    verdicts = (
        RaterVerdict(rater="a", grade="high", reasoning="steady state"),
        RaterVerdict(rater="b", grade="high", reasoning="no commitment recorded"),
    )

    rendered = "\n".join(render_confidence_reasoning(verdicts))

    assert "steady state" in rendered
    assert "no commitment recorded" in rendered
    assert "steady state; no commitment recorded" not in rendered


def test_an_unrated_driver_claims_no_reasoning():
    assert render_confidence_reasoning(()) == []
