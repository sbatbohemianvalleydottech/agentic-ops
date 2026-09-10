"""The report is what a reviewer actually reads, so what it omits matters as much
as what it says. Empty sections render as empty rather than disappearing, because
"checked, found nothing" and "never checked" are different claims.
"""

from datetime import datetime
from decimal import Decimal

from cost_agent.classify import classify
from cost_agent.drivers import build_analysis
from cost_agent.inputs import Inputs, Resource, Unmatched
from cost_agent.report import render_report
from cost_agent.savings import estimate_savings
from cost_agent.thresholds import load_thresholds

THRESHOLDS = load_thresholds()
AS_OF = datetime(2026, 9, 1)


def resource(resource_id, cost, **overrides) -> Resource:
    base = dict(
        resource_id=resource_id, cloud="gcp", service="anything",
        period_cost=Decimal(cost), kind="compute", tags={"owner": "platform"},
        utilisation_avg=0.75, age_days=100, attached=True, commitment_covered=True,
    )
    return Resource(**{**base, **overrides})


def report_for(resources, unmatched=()) -> str:
    total = sum((r.period_cost for r in resources), Decimal("0"))
    inputs = Inputs(tuple(resources), tuple(unmatched), total)
    analysis = build_analysis(classify(inputs, THRESHOLDS, AS_OF), inputs, THRESHOLDS)
    costs = {
        r.resource_id: (r.period_cost * THRESHOLDS.annualisation_multiplier)
        for r in resources
    }
    analysis = analysis.__class__(
        **{
            **analysis.__dict__,
            "drivers": tuple(
                estimate_savings(d, costs, THRESHOLDS) for d in analysis.drivers
            ),
        }
    )
    return render_report(analysis)


def test_every_driver_renders_all_seven_required_fields():
    report = report_for([
        resource("r-a", "5000.00", utilisation_avg=0.20),
        resource("r-b", "4000.00", utilisation_avg=0.25),
    ])

    for label in (
        "Cloud", "Annual cost", "Share of bill", "Root cause",
        "Savings", "Confidence", "What would change",
        "Question needed to confirm",
    ):
        assert label in report, f"{label} missing from the driver block"


def test_a_contested_resource_names_the_winner_the_alternative_and_the_basis():
    report = report_for([
        resource("r-both", "1000.00", kind="storage", tier="standard",
                 attached=False, age_days=300, utilisation_avg=0.10),
        resource("r-other", "500.00", utilisation_avg=0.20),
    ])

    assert "r-both" in report
    assert "WORKLOAD_ELIMINATION" in report
    assert "CAPACITY_MANAGEMENT" in report
    assert "outranks" in report


def test_the_contested_section_is_present_and_empty_when_nothing_overlaps():
    """A reader has to be able to tell 'checked, none found' from 'not checked'."""
    report = report_for([
        resource("r-a", "5000.00", utilisation_avg=0.20),
        resource("r-b", "4000.00", utilisation_avg=0.25),
    ])

    assert "Contested attributions" in report
    assert "none" in report.lower()


def test_unassessable_and_unmatched_sections_render_even_when_empty():
    report = report_for([resource("r-a", "5000.00", utilisation_avg=0.20)])

    assert "Unassessable" in report
    assert "Unmatched" in report


def test_unmatched_resources_appear_with_which_side_they_came_from():
    report = report_for(
        [resource("r-a", "5000.00", utilisation_avg=0.20)],
        unmatched=[Unmatched("r-ghost", "cost_export", Decimal("42.00"))],
    )

    assert "r-ghost" in report
    assert "cost_export" in report


def test_the_annualisation_multiplier_is_stated_alongside_the_figure():
    """365/30 versus 12 moves the headline by 1.4%. Stating it removes an argument."""
    report = report_for([resource("r-a", "5000.00", utilisation_avg=0.20)])

    assert str(THRESHOLDS.annualisation_multiplier) in report


def test_a_single_resource_driver_is_flagged_in_the_output():
    report = report_for([
        resource("r-alone", "1000.00", kind="storage", tier="standard",
                 attached=False, age_days=300, utilisation_avg=None),
        resource("r-a", "500.00", utilisation_avg=0.20),
        resource("r-b", "500.00", utilisation_avg=0.25),
    ])

    assert "one resource" in report.lower()
