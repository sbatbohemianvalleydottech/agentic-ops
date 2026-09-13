"""Rendering.

This is the only part a human ever reads, and in this repository it is the part
that has twice thrown away work the logic underneath got right. So the rules it
follows are explicit: no total without its coverage beneath it, every priced line
carrying what priced it, every finding naming its attribute, and no value the
plan marked sensitive anywhere in the output.
"""

from __future__ import annotations

import textwrap
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from .coverage import Bucket, Summary
from .gate import Decision
from .policy import Policy
from .prices import PriceTable
from .pricing import PricedPlan
from .rules import Finding

LABELS = {
    Bucket.UNKNOWN_UNTIL_APPLY: "unknown until apply",
    Bucket.NO_PRICE_ROW: "no price row",
    Bucket.NOT_PRICEABLE: "not priceable",
    Bucket.NO_CHANGE: "no change",
}

UNCOUNTED = (
    Bucket.UNKNOWN_UNTIL_APPLY,
    Bucket.NO_PRICE_ROW,
    Bucket.NOT_PRICEABLE,
    Bucket.NO_CHANGE,
)


def money(amount: Decimal) -> str:
    return f"{'-' if amount < 0 else '+'}${abs(amount):,.2f}"


def render(
    *,
    plan_path: Path,
    priced: PricedPlan,
    findings: Sequence[Finding],
    decision: Decision,
    table: PriceTable,
    policy: Policy,
    threshold_note: str = "",
) -> str:
    lines = [f"PLAN COST  {plan_path}", ""]
    lines += _heading(priced, decision, table)
    lines += _priced(priced)
    lines += _not_counted(priced.coverage)
    lines += _findings(findings)
    lines += _decision(decision, policy, threshold_note, has_figure=priced.has_figure)
    # No trailing whitespace: the report is pasted into pull requests and diffs.
    return "\n".join(line.rstrip() for line in lines)


def _heading(priced: PricedPlan, decision: Decision, table: PriceTable) -> list[str]:
    lines = [f"  Environment      {decision.environment} (from {decision.environment_source})"]
    if priced.has_figure:
        taken = f", oldest row taken {table.oldest}" if table.oldest else ""
        lines.append(f"  Monthly change   {money(priced.total)}")
        lines.append(f"                   730 hours per month, list prices{taken}")
    else:
        lines.append("  Monthly change   nothing here can be priced")
    return lines + [""]


def _priced(priced: PricedPlan) -> list[str]:
    if not priced.lines:
        return []
    lines = ["  Priced"]
    for line in priced.lines:
        lines.append(f"    {line.address:<44}{money(line.delta):>12}   {line.detail}")
    return lines + [""]


def _not_counted(coverage: Summary) -> list[str]:
    lines = ["  Not counted"]
    for bucket in UNCOUNTED:
        count = coverage.counts.get(bucket, 0)
        if not count:
            continue
        lines.append(f"    {LABELS[bucket]:<21}{count:>3}   {_why(coverage, bucket)}")
    total = len(coverage.buckets)
    counted = sum(coverage.counts.values())
    return lines + ["", f"  {total} resource changes, {counted} accounted for.", ""]


def _why(coverage: Summary, bucket: Bucket) -> str:
    reasons = [
        reason
        for reason, in_bucket in zip(coverage.reasons, coverage.buckets, strict=True)
        if in_bucket is bucket and reason
    ]
    if not reasons:
        return ""
    if bucket is Bucket.NOT_PRICEABLE:
        counted = Counter(reasons)
        return ", ".join(f"{reason} {n}" for reason, n in sorted(counted.items()))
    unique = list(dict.fromkeys(reasons))
    shown = ", ".join(unique[:2])
    return shown if len(unique) <= 2 else f"{shown}, and {len(unique) - 2} more"


def _findings(findings: Sequence[Finding]) -> list[str]:
    lines = ["FINDINGS", ""]
    if not findings:
        return lines + ["  Nothing fired.", ""]
    for finding in findings:
        lines.append(f"  {finding.severity:<7} {finding.rule:<31} {finding.address}")
        if finding.value is None:
            lines.append(
                f"          {finding.attribute}, value not shown "
                "because the plan marks it sensitive"
            )
        else:
            lines.append(f"          {finding.attribute} {finding.value}")
        lines.append(f"          {finding.why}")
        lines.append("")
    return lines


def _decision(
    decision: Decision, policy: Policy, threshold_note: str, *, has_figure: bool
) -> list[str]:
    blocking = sorted(name for name, action in policy.environments.items() if action == "block")
    if decision.blocked:
        headline = "blocked"
    elif decision.would_have_blocked:
        where = " or ".join(blocking) if blocking else "an environment that blocks"
        headline = f"reported, would have blocked in {where}"
    else:
        headline = "not blocked"

    if decision.rule_fired:
        rule = f"yes, {decision.rule_fired}"
    else:
        rule = "no, nothing fired at a blocking severity"

    if has_figure:
        comparison = "over" if decision.over_threshold else "at or under"
        threshold = (
            f"{'yes' if decision.over_threshold else 'no'}, {money(decision.total)} "
            f"{comparison} ${decision.threshold:,.2f}"
        )
    else:
        # Zero is not the answer here. Nothing in this plan could be priced, and
        # printing a figure would invent one.
        threshold = "no figure to compare, nothing here could be priced"

    lines = [
        f"DECISION  {headline}",
        "",
        f"  rule fired at blocking severity   {rule}",
        f"  monthly change over threshold     {threshold}",
    ]
    for chunk in textwrap.wrap(threshold_note, width=74):
        lines.append(f"                                    {chunk}")
    lines += [
        f"  environment policy                {decision.environment} "
        f"{'blocks' if decision.policy == 'block' else 'reports'}",
        "",
        f"  exit {1 if decision.blocked else 0}",
    ]
    return lines
