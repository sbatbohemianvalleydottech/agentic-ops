"""Render the analysis as a plain-text report.

Empty sections still render. "Checked, found nothing" and "never checked" are
different claims, and a reader cannot tell them apart from an absent heading.
"""

from decimal import Decimal

from ensemble.explain import wrap

from .drivers import Analysis, Driver


def _money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _count(number: int, noun: str) -> str:
    """"1 resource", not "1 resources". A report that cannot count in English
    invites the reader to wonder what else it cannot count."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _pct(fraction: Decimal) -> str:
    return f"{fraction * 100:.1f}%"


def render_confidence_reasoning(verdicts) -> list[str]:
    """Why each assessor rated it that way, kept apart per model.

    Two raters returning `high` is not two raters agreeing. Whether they got
    there by the same argument is the correlated-failure question, and joining
    the strings is what destroyed that distinction before any report saw it.
    """
    lines: list[str] = []
    for verdict in verdicts:
        lines += [
            f"    {verdict.rater} said {verdict.grade}",
            *wrap(verdict.reasoning, indent=6),
        ]
    return lines


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
        *render_confidence_reasoning(driver.confidence_raters),
        f"  What would change it:       {driver.what_would_change_confidence}",
        f"  Question needed to confirm: {driver.confirming_question}",
        f"  Explains:                   "
        f"{_count(len({f.resource_id for f in driver.findings}), 'resource')}, "
        f"{_count(len(driver.findings), 'finding')}",
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


def _savings_total(analysis) -> list[str]:
    """The identified saving, split by whether anything is waiting on a date.

    A driver whose resources are scheduled to go away already prints its
    horizon. Adding the driver ranges together lost that: the sum reads as one
    number available to whoever is asking, when a share of it cannot arrive
    until somebody else's decommission lands. On a real estate that share was
    two thirds, and the difference between 38% and 12.6% of the bill is the
    difference between a plan and a wish.
    """
    dated = [d for d in analysis.drivers if d.decommission_horizon]
    undated = [d for d in analysis.drivers if not d.decommission_horizon]

    def total(drivers, field):
        return sum((getattr(d, field) for d in drivers), Decimal("0"))

    low, high = total(analysis.drivers, "savings_low"), total(analysis.drivers, "savings_high")
    if not low and not high:
        return []

    def band(a: Decimal, b: Decimal) -> str:
        if not analysis.total_bill_annual:
            return ""
        low_pct = a / analysis.total_bill_annual * 100
        high_pct = b / analysis.total_bill_annual * 100
        return f" ({low_pct:.1f}% to {high_pct:.1f}%)"

    now_low, now_high = total(undated, "savings_low"), total(undated, "savings_high")
    lines = [
        "",
        f"Identified savings:         {_money(low)} to {_money(high)}{band(low, high)}",
        f"  available now             {_money(now_low)} to {_money(now_high)}"
        f"{band(now_low, now_high)}",
    ]
    if dated:
        dl, dh = total(dated, "savings_low"), total(dated, "savings_high")
        horizon = max(d.decommission_horizon for d in dated)
        lines.append(
            f"  behind a scheduled date   {_money(dl)} to {_money(dh)}{band(dl, dh)},"
            f" the last {horizon}"
        )
    else:
        lines.append("  behind a scheduled date   none")
    return lines


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
    ]
    lines += _savings_total(analysis)
    lines += [
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

    # Rendered whether or not anything is in it, like every section above.
    # An absent heading and "checked, found nothing" are different claims.
    lines.append("")
    if analysis.healthy:
        lines.append(
            f"Healthy: {_count(len(analysis.healthy), 'resource')} produced no finding."
        )
    else:
        lines.append("Healthy: none. Every resource produced at least one finding.")

    return "\n".join(lines)
