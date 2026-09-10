"""Savings are a range, never a point.

The tool can see utilisation. It cannot see contracts, reserved capacity, warm
standbys or compliance holds. A point estimate would claim knowledge it does not
have, so the range and the confirming question are the honest part of the output.
"""

from decimal import Decimal

from cost_agent.classify import Finding, RootCause, Rule
from cost_agent.drivers import Driver
from cost_agent.savings import estimate_savings
from cost_agent.thresholds import load_thresholds

THRESHOLDS = load_thresholds()


def finding(resource_id, rule, fraction) -> Finding:
    return Finding(
        resource_id=resource_id,
        rule=rule,
        observed={},
        recoverable_fraction=Decimal(fraction),
    )


def driver_with(*findings) -> Driver:
    return Driver(
        root_cause=RootCause.CAPACITY_MANAGEMENT,
        absent_practice="capacity is never revisited",
        cloud="gcp",
        findings=tuple(findings),
        annual_cost=Decimal("10000.00"),
        share_of_bill=Decimal("0.5"),
        single_resource=False,
    )


def test_savings_is_a_range_with_a_conservative_lower_bound():
    driver = estimate_savings(
        driver_with(finding("r-1", Rule.UNDER_UTILISED, "0.30")),
        {"r-1": Decimal("10000.00")},
        THRESHOLDS,
    )

    assert driver.savings_low < driver.savings_high
    assert driver.savings_low > 0


def test_two_findings_on_one_resource_are_not_counted_twice():
    """Under-utilised and oversized describe the same slack. Adding them would
    claim more headroom than the resource has."""
    both = estimate_savings(
        driver_with(
            finding("r-1", Rule.UNDER_UTILISED, "0.30"),
            finding("r-1", Rule.OVERSIZED, "0.25"),
        ),
        {"r-1": Decimal("10000.00")},
        THRESHOLDS,
    )
    single = estimate_savings(
        driver_with(finding("r-1", Rule.UNDER_UTILISED, "0.30")),
        {"r-1": Decimal("10000.00")},
        THRESHOLDS,
    )

    assert both.savings_high == single.savings_high


def test_savings_never_exceed_the_cost_of_the_resources_it_explains():
    driver = estimate_savings(
        driver_with(finding("r-1", Rule.STALE_UNATTACHED, "1.00")),
        {"r-1": Decimal("10000.00")},
        THRESHOLDS,
    )

    assert driver.savings_high <= Decimal("10000.00")


def test_percentages_agree_with_the_amounts():
    driver = estimate_savings(
        driver_with(finding("r-1", Rule.UNDER_UTILISED, "0.30")),
        {"r-1": Decimal("10000.00")},
        THRESHOLDS,
    )

    assert driver.savings_pct_high == (
        driver.savings_high / driver.annual_cost
    ).quantize(Decimal("0.0001"))


def test_a_driver_carries_a_confirming_question():
    """The tool cannot see contracts or intent, and the question is where the
    analysis honestly stops."""
    driver = estimate_savings(
        driver_with(finding("r-1", Rule.UNDER_UTILISED, "0.30")),
        {"r-1": Decimal("10000.00")},
        THRESHOLDS,
    )

    assert driver.confirming_question
    assert driver.what_would_change_confidence
