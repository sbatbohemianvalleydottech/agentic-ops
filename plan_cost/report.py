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
from .refresh import CATALOGUE_SOURCE
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
    prices_path: Path,
    threshold_note: str = "",
) -> str:
    lines = [f"PLAN COST  {plan_path}", ""]
    lines += _heading(priced, decision, table, prices_path)
    lines += _priced(priced)
    lines += _not_counted(priced.coverage)
    lines += _missing_rows(priced.coverage.missing_keys, prices_path)
    lines += _findings(findings)
    lines += _decision(decision, policy, threshold_note, has_figure=priced.has_figure)
    # No trailing whitespace: the report is pasted into pull requests and diffs.
    return "\n".join(line.rstrip() for line in lines)


def _heading(
    priced: PricedPlan, decision: Decision, table: PriceTable, prices_path: Path
) -> list[str]:
    lines = [f"  Environment      {decision.environment} (from {decision.environment_source})"]
    if priced.has_figure:
        taken = f", oldest row taken {table.oldest}" if table.oldest else ""
        lines.append(f"  Monthly change   {money(priced.total)}")
        # Name the table rather than calling its contents list prices. What
        # kind of rates they are is a per row fact, and the table carries it.
        lines.append(
            f"                   730 hours per month, rates from {prices_path.name}{taken}"
        )
        # Said every run, because a reader looking at a node pool figure will
        # otherwise assume the disks under it are in there.
        lines.append("                   compute priced by machine type; storage attached")
        lines.append("                   inside an instance or node pool is not included")
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


def _coverage_line(total: int, counted: int) -> str:
    """"1 resource change", not "1 resource changes".

    Real plans are frequently a single resource; both shipped fixtures have
    twelve, so this read wrong on the first real plan and on none of the tests.
    A report whose job is arithmetic should be able to count in English.
    """
    noun = "resource change" if total == 1 else "resource changes"
    return f"  {total} {noun}, {counted} accounted for."


def _not_counted(coverage: Summary) -> list[str]:
    lines = []
    for bucket in UNCOUNTED:
        count = coverage.counts.get(bucket, 0)
        if not count:
            continue
        lines.append(f"    {LABELS[bucket]:<21}{count:>3}   {_why(coverage, bucket)}")
    # A heading with nothing under it reads as a bug, and on a plan where
    # everything priced there is genuinely nothing to say here.
    if lines:
        lines = ["  Not counted", *lines, ""]
    total = len(coverage.buckets)
    counted = sum(coverage.counts.values())
    return lines + [_coverage_line(total, counted), ""]


# A gate report is pasted into pull requests. Forty lines of price keys is not
# a report, and the refresh adds every key in the catalogue rather than only the
# ones listed, so a capped list costs the reader nothing.
MOST_KEYS_SHOWN = 10


def _short(path: Path) -> str:
    """The path as someone in this directory would type it.

    The default price table resolves to an absolute path, so printing it raw
    puts whoever ran the tool's home directory into a report that gets pasted
    into pull requests. Relative to the working directory it is still runnable
    as printed, from the same place every documented command is run from.
    """
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _missing_rows(missing_keys: Sequence[str], prices_path: Path) -> list[str]:
    """What to do about a key that had no row.

    Kept out of the Not counted block above: that block counts and this one
    instructs, and the coverage arithmetic stays one clean line.

    Two commands, because the operator has no catalogue file yet and a command
    assuming an input they do not have is a description of a command. The URL
    comes from the refresher rather than a copy of it, so the printed command
    cannot drift from the one it describes, and the second names the table
    actually in use rather than the shipped default.
    """
    if not missing_keys:
        return []
    lines = ["  Missing price rows"]
    lines += [f"    {key}" for key in missing_keys[:MOST_KEYS_SHOWN]]
    if len(missing_keys) > MOST_KEYS_SHOWN:
        lines.append(f"    and {len(missing_keys) - MOST_KEYS_SHOWN} more")
    return lines + [
        "  Fetch a catalogue and add them:",
        '    curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \\',
        f'      "{CATALOGUE_SOURCE}" > skus.json',
        f"    .venv/bin/python -m plan_cost --refresh-prices skus.json "
        f"--prices {_short(prices_path)}",
        "  That rewrites the table in place, so copy it first if that matters.",
        "",
    ]


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
