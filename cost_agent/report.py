"""Render the analysis as a plain-text report.

Empty sections still render. "Checked, found nothing" and "never checked" are
different claims, and a reader cannot tell them apart from an absent heading.
"""

from decimal import Decimal

from .drivers import Analysis, Driver


def _money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _pct(fraction: Decimal) -> str:
    return f"{fraction * 100:.1f}%"


def _driver_block(index: int, driver: Driver) -> list[str]:
    lines = [
        f"DRIVER {index}: {driver.root_cause.name}",
        f"  Cloud:                      {driver.cloud}",
        f"  Annual cost:                {_money(driver.annual_cost)}",
        f"  Share of bill:              {_pct(driver.share_of_bill)}",
        f"  Root cause:                 {driver.absent_practice}",
        f"  Savings:                    {_money(driver.savings_low)} to "
        f"{_money(driver.savings_high)} "
        f"({_pct(driver.savings_pct_low)} to {_pct(driver.savings_pct_high)})",
        f"  Confidence:                 {driver.confidence}",
        f"  What would change it:       {driver.what_would_change_confidence}",
        f"  Question needed to confirm: {driver.confirming_question}",
        f"  Explains:                   {len({f.resource_id for f in driver.findings})} "
        f"resources, {len(driver.findings)} findings",
    ]

    if driver.decommission_horizon:
        # The saving is real and it is not this quarter's. Keeping the date next
        # to the number stops the number travelling without it.
        lines.insert(
            6,
            f"  Realised at:                {driver.decommission_horizon}, when the "
            "last of these workloads is scheduled to go",
        )

    if driver.single_resource:
        lines.append(
            "  NOTE:                       explains one resource only, so this is "
            "closer to a line item than a structural driver."
        )

    return lines + [""]


def render_report(
    analysis: Analysis, models: tuple[str, str, str] | None = None
) -> str:
    lines = [
        "COST DRIVER ANALYSIS",
        "",
        f"Annualised bill:            {_money(analysis.total_bill_annual)}",
        f"Annualisation multiplier:   {analysis.annualisation_multiplier} "
        "(monthly to annual, stated because 12 would understate it by ~1.4%)",
        "",
        "=" * 72,
        "",
    ]

    if models:
        # What produced a confidence rating is the first thing an audit asks.
        lines += [
            f"Confidence assessed by {models[0]} and {models[1]},",
            f"judged by {models[2]}.",
            "",
        ]

    for index, driver in enumerate(analysis.drivers, start=1):
        lines += _driver_block(index, driver)

    attributed = sum((d.annual_cost for d in analysis.drivers), Decimal("0"))
    lines += [
        "=" * 72,
        "",
        f"Attributed to drivers:      {_money(attributed)} of "
        f"{_money(analysis.total_bill_annual)}",
        "Every dollar belongs to exactly one driver, so these never sum past the bill.",
        "",
        "Contested attributions",
        "  Resources matching more than one root cause. Assigned to the highest, with",
        "  the alternative recorded, so the judgement call is inspectable.",
    ]

    if analysis.contested:
        for contest in analysis.contested:
            lines += [
                f"  - {contest.resource_id} -> {contest.assigned_to.name}",
                f"      also matched: "
                f"{', '.join(c.name for c in contest.also_matched)}",
                f"      basis: {contest.basis}",
            ]
    else:
        lines.append("  none: no resource matched more than one root cause.")

    lines += ["", "Unassessable", "  Utilisation data missing, so not classifiable."]
    if analysis.unassessable:
        for finding in analysis.unassessable:
            lines.append(f"  - {finding.resource_id}")
    else:
        lines.append("  none.")

    lines += [
        "",
        "Unmatched",
        "  Present in one input but not the other. Reported rather than dropped:",
        "  unpriced resources and unattributed spend are findings in themselves.",
    ]
    if analysis.unmatched:
        for item in analysis.unmatched:
            cost = _money(item.period_cost) if item.period_cost else "no cost recorded"
            lines.append(f"  - {item.resource_id} (only in {item.present_in}, {cost})")
    else:
        lines.append("  none.")

    if analysis.healthy:
        lines += [
            "",
            f"Healthy: {len(analysis.healthy)} resources produced no finding.",
        ]

    return "\n".join(lines)
