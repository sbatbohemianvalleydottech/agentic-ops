"""A run that flags everything says so, and says what it might mean.

Found by running the analyser on a real estate where 13 of 13 resources came
back with a finding: nothing healthy, nothing unmatched. The report said
"Healthy: none. Every resource produced at least one finding", which is true and
reads as thoroughness. It is equally consistent with thresholds loose enough to
match anything, and a ranking built from thresholds that match anything
separates nothing.

The tool holds both numbers and does the division nowhere. It also cannot tell
which of the two explanations is right, so it states the ambiguity rather than
resolving it. Resolving it needs evidence the tool does not have.

Assessed means checked. Unassessable resources were never checked at all, so
counting them would inflate the claim, and unmatched resources are present in
one input only.
"""

from decimal import Decimal

import pytest

from cost_agent.classify import classify
from cost_agent.drivers import build_analysis
from cost_agent.inputs import Inputs
from cost_agent.report import render_report

NOTE = "assessed resources produced at least one finding"


@pytest.fixture
def report_for(thresholds, as_of):
    """The report with its line breaks flattened.

    The note is wrapped to the page, so where it breaks depends on how many
    digits the count has. Asserting on the sentence rather than on the wrapping
    keeps these tests about the claim.
    """

    def _report(resources, unmatched=()) -> str:
        total = sum((r.period_cost for r in resources), Decimal("0"))
        inputs = Inputs(tuple(resources), tuple(unmatched), total)
        analysis = build_analysis(classify(inputs, thresholds, as_of), inputs, thresholds)
        return " ".join(render_report(analysis).split())

    return _report


def wasteful(make_resource, resource_id):
    """Idle, so it fires a rule with a root cause behind it."""
    return make_resource(resource_id, "1000.00", utilisation_avg=0.02)


def unassessable(make_resource, resource_id):
    """No utilisation data, so it was never checked against anything."""
    return make_resource(resource_id, "1000.00", utilisation_avg=None)


def test_an_estate_where_everything_fired_says_so(report_for, make_resource):
    report = report_for([wasteful(make_resource, f"r-{n}") for n in range(13)])
    assert NOTE in report


def test_it_names_the_count(report_for, make_resource):
    report = report_for([wasteful(make_resource, f"r-{n}") for n in range(13)])
    assert "All 13 assessed resources" in report


def test_one_healthy_resource_suppresses_it_entirely(report_for, make_resource):
    """Not a softened note. The claim is false, so it does not appear."""
    resources = [wasteful(make_resource, f"r-{n}") for n in range(12)]
    resources.append(make_resource("fine", "1000.00"))
    assert NOTE not in report_for(resources)


def test_below_three_assessed_it_does_not_appear(report_for, make_resource):
    """Two out of two says nothing about thresholds."""
    assert NOTE not in report_for([wasteful(make_resource, f"r-{n}") for n in range(2)])


def test_at_three_assessed_it_does_appear(report_for, make_resource):
    """The other side of the same boundary. A one-sided test passes on an
    off-by-one, and the population minimum is the one number here that was
    chosen rather than derived."""
    report = report_for([wasteful(make_resource, f"r-{n}") for n in range(3)])
    assert NOTE in report
    assert "All 3 assessed resources" in report


def test_an_empty_estate_renders_and_says_nothing(report_for):
    report = report_for([])
    assert NOTE not in report
    assert "COST DRIVER ANALYSIS" in report


def test_unassessable_resources_are_not_counted_as_assessed(report_for, make_resource):
    """Three checked and flagged, two never checked. The claim is about three."""
    resources = [wasteful(make_resource, f"r-{n}") for n in range(3)]
    resources += [unassessable(make_resource, f"u-{n}") for n in range(2)]
    report = report_for(resources)
    assert "All 3 assessed resources" in report
    assert "All 5 assessed resources" not in report


def test_unassessable_alone_does_not_trigger_the_note(report_for, make_resource):
    """Nothing was assessed, so there is no saturation to report."""
    assert NOTE not in report_for([unassessable(make_resource, f"u-{n}") for n in range(5)])


def test_unmatched_resources_are_not_counted_as_assessed(
    report_for, make_resource, thresholds
):
    from cost_agent.inputs import Unmatched

    resources = [wasteful(make_resource, f"r-{n}") for n in range(3)]
    unmatched = [
        Unmatched(resource_id=f"only-in-costs-{n}", present_in="costs", period_cost=Decimal("5"))
        for n in range(4)
    ]
    report = report_for(resources, unmatched=unmatched)
    assert "All 3 assessed resources" in report


def test_the_healthy_line_survives_when_there_are_healthy_resources(
    report_for, make_resource
):
    """Unchanged behaviour. This is the branch the note does not touch."""
    resources = [wasteful(make_resource, f"r-{n}") for n in range(3)]
    resources.append(make_resource("fine", "1000.00"))
    assert "Healthy: 1 resource produced no finding." in report_for(resources)


def test_the_note_offers_both_explanations_without_choosing(report_for, make_resource):
    """A tool that cannot tell which is true must not imply it can."""
    report = report_for([wasteful(make_resource, f"r-{n}") for n in range(13)])
    assert "the estate is uniformly poor" in report
    # Named, because "check your thresholds" is not an instruction and a
    # filename is.
    assert "thresholds.toml are loose enough to match everything" in report
