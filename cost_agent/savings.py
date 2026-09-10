"""Estimate what a driver could return, as a range.

Never a point. The tool observes utilisation; it cannot see contractual terms,
reserved capacity, a workload that looks idle because it is a warm standby, or a
compliance reason a bucket cannot be tiered. A single number would claim
knowledge it does not have. The range plus the confirming question is where the
analysis honestly stops, and that boundary is the most credible thing in it.
"""

from dataclasses import replace
from decimal import Decimal

from .classify import RootCause
from .drivers import Driver
from .thresholds import Thresholds

CENTS = Decimal("0.01")
PCT = Decimal("0.0001")

WHAT_WOULD_CHANGE = {
    RootCause.WORKLOAD_ELIMINATION: (
        "Whether anything still depends on these resources. A volume detached for "
        "months can still be the only copy of something."
    ),
    RootCause.RETENTION_LIFECYCLE: (
        "Whether a retention obligation or an audit requirement forces this data to "
        "stay on its current tier."
    ),
    RootCause.CAPACITY_MANAGEMENT: (
        "Whether average utilisation hides a peak. Right-sizing against an average "
        "is how a saving becomes an outage."
    ),
    RootCause.COMMERCIAL: (
        "Whether existing agreements already cover this spend, and whether the "
        "workload is stable enough to commit to for a term."
    ),
}

CONFIRMING_QUESTION = {
    RootCause.WORKLOAD_ELIMINATION: (
        "Who owns these resources, and what breaks if they are deleted this quarter?"
    ),
    RootCause.RETENTION_LIFECYCLE: (
        "What is the retention obligation on this data, and who signs off on tiering it?"
    ),
    RootCause.CAPACITY_MANAGEMENT: (
        "What is the observed peak rather than the average, and what headroom does the "
        "service level require above it?"
    ),
    RootCause.COMMERCIAL: (
        "What commitments and enterprise terms already exist, and when do they renew?"
    ),
}


def estimate_savings(
    driver: Driver,
    annual_cost_by_resource: dict[str, Decimal],
    thresholds: Thresholds,
) -> Driver:
    # Several rules can fire on one resource and describe the same slack.
    # Under-utilised and oversized are two readings of one gap, so the largest
    # fraction wins rather than the sum, which would claim more headroom than the
    # resource has.
    best: dict[str, Decimal] = {}
    for finding in driver.findings:
        current = best.get(finding.resource_id, Decimal("0"))
        best[finding.resource_id] = max(current, finding.recoverable_fraction)

    high = sum(
        (
            annual_cost_by_resource.get(resource_id, Decimal("0")) * fraction
            for resource_id, fraction in best.items()
        ),
        Decimal("0"),
    ).quantize(CENTS)

    low = (high * thresholds.savings_conservatism).quantize(CENTS)

    def pct(amount: Decimal) -> Decimal:
        if not driver.annual_cost:
            return Decimal("0")
        return (amount / driver.annual_cost).quantize(PCT)

    return replace(
        driver,
        savings_low=low,
        savings_high=high,
        savings_pct_low=pct(low),
        savings_pct_high=pct(high),
        what_would_change_confidence=WHAT_WOULD_CHANGE[driver.root_cause],
        confirming_question=CONFIRMING_QUESTION[driver.root_cause],
    )
