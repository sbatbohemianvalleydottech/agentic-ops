"""Savings behind a scheduled date are totalled apart from savings available now.

The report already prints a horizon beside the driver that has one, because
"eliminable" and "eliminable by end-2028" are different claims and only the
second is true. It then lost that distinction at the bottom of the page: a
reader adding the four driver ranges got one number, and nothing said what
share of it was waiting on a decommission somebody else controls.

Found by running this against an estate where a dated elimination driver
dominates. Neither shipped fixture has that shape, so the fixtures could not
have caught it: in estate_a the eliminable driver is under 2% of the bill, and
the error is invisible at that size. On an estate where it is a quarter of the
bill, two thirds of the headline saving turned out to be unavailable for two
years, and the headline did not say so.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from cost_agent.classify import classify
from cost_agent.drivers import build_analysis
from cost_agent.inputs import Inputs
from cost_agent.report import render_report
from cost_agent.savings import estimate_savings


@pytest.fixture
def report_for(thresholds, as_of):
    def _report(resources) -> str:
        total = sum((r.period_cost for r in resources), Decimal("0"))
        inputs = Inputs(tuple(resources), (), total)
        analysis = build_analysis(classify(inputs, thresholds, as_of), inputs, thresholds)
        annual = {
            r.resource_id: r.period_cost * thresholds.annualisation_multiplier
            for r in resources
        }
        from dataclasses import replace

        analysis = replace(
            analysis,
            drivers=tuple(
                estimate_savings(d, annual, thresholds) for d in analysis.drivers
            ),
        )
        return render_report(analysis)

    return _report


@pytest.fixture
def mixed(make_resource):
    """One big resource going away in 2028, one small one wasting money now."""
    return [
        make_resource(
            "leaving-2028", "40000.00", utilisation_avg=0.20,
            decommission_at=datetime(2028, 12, 31),
        ),
        make_resource("wasteful-now", "4000.00", utilisation_avg=0.20),
    ]


def test_the_total_is_reported(report_for, mixed):
    assert "Identified savings" in report_for(mixed)


def test_the_total_separates_what_is_available_now(report_for, mixed):
    report = report_for(mixed)
    assert "available now" in report


def test_the_total_names_the_share_waiting_on_a_date(report_for, mixed):
    report = report_for(mixed)
    assert "behind a scheduled date" in report
    assert "2028-12-31" in report


def test_an_estate_with_no_scheduled_date_says_so_rather_than_printing_zero(
    report_for, make_resource
):
    """Every category renders. A zero here is a claim, and it has to be legible."""
    report = report_for([make_resource("wasteful-now", "4000.00", utilisation_avg=0.20)])
    assert "Identified savings" in report
    line = next(ln for ln in report.splitlines() if "behind a scheduled date" in ln)
    assert line.strip().endswith("none")


def test_the_two_parts_add_up_to_the_total(report_for, mixed):
    """If they do not, the split is decoration."""
    import re

    report = report_for(mixed)
    line = next(ln for ln in report.splitlines() if "Identified savings" in ln)
    now = next(ln for ln in report.splitlines() if "available now" in ln)
    later = next(ln for ln in report.splitlines() if "behind a scheduled date" in ln)

    def amounts(text):
        return [Decimal(m.replace(",", "")) for m in re.findall(r"\$([\d,]+\.\d\d)", text)]

    total_low, total_high = amounts(line)
    now_low, now_high = amounts(now)
    later_low, later_high = amounts(later)

    assert now_low + later_low == total_low
    assert now_high + later_high == total_high


def test_the_dated_driver_is_the_larger_share_here(report_for, mixed):
    """Guards the fixture: if this stops holding, the example stops demonstrating."""
    import re

    report = report_for(mixed)
    now = next(ln for ln in report.splitlines() if "available now" in ln)
    later = next(ln for ln in report.splitlines() if "behind a scheduled date" in ln)
    def high(text):
        return Decimal(re.findall(r"\$([\d,]+\.\d\d)", text)[1].replace(",", ""))

    assert high(later) > high(now)
