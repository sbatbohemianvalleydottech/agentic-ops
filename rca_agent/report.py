"""Render a review for a human.

Defects carry their quote, because the point of a finding is that someone can
check it against the document without rerunning anything. Contested judgement
dimensions are named as contested rather than quietly omitted.
"""

from .completion import CompletionReport
from .judgement import DimensionGrade
from .structure import Review


def render_review(
    review: Review,
    grades: list[DimensionGrade] | None = None,
    models: tuple[str, str, str] | None = None,
) -> str:
    lines = [f"RCA {review.rca_id}", ""]

    if not review.defects:
        lines.append("  No structural defects.")
    else:
        by_dimension: dict[str, list] = {}
        for defect in review.defects:
            by_dimension.setdefault(defect.dimension.value, []).append(defect)

        for dimension, defects in by_dimension.items():
            lines.append(f"  {dimension} ({len(defects)})")
            for defect in defects:
                lines += [f"    - {defect.detail}", f'      "{defect.quote}"']
            lines.append("")

    if review.requires_human_judgement:
        lines += [
            "  NEEDS HUMAN JUDGEMENT: this review produced no action items at all.",
            "  Either the incident was trivial or it was never really reviewed, and",
            "  no automated check can tell you which.",
            "",
        ]

    if models:
        # The first question an audit asks about an automated judgement is what
        # produced it. The ledger knows; the report is what people read.
        lines += [
            f"  Assessed by {models[0]} and {models[1]}, judged by {models[2]}",
            "",
        ]

    if grades:
        lines += ["  Judgement dimensions", ""]
        for grade in grades:
            if grade.needs_human_review:
                lines += [
                    f"    {grade.dimension.value}: CONTESTED, needs human review",
                    f"      {grade.reasoning}",
                ]
            else:
                lines.append(f"    {grade.dimension.value}: {grade.grade}")
        lines.append("")

    return "\n".join(lines)


def render_completion(report: CompletionReport) -> str:
    median = (
        f"{report.median_open_age_days} days"
        if report.median_open_age_days is not None
        else "nothing open"
    )

    lines = [
        "ACTION ITEM COMPLETION",
        "",
        f"  Items:                    {report.total_items}",
        f"  Closed:                   {report.closed_items} "
        f"({report.closure_rate * 100:.0f}%)",
        f"  Median age of open items: {median}",
        f"  Closed with no evidence:  {report.closed_without_evidence}",
        "",
    ]

    lines.append("  Export policy breaches")
    lines.append(
        "    Follow-ups not in a tracker beyond the window after closure."
    )
    if report.export_policy_breaches:
        lines += [f"    - {rca_id}" for rca_id in report.export_policy_breaches]
    else:
        lines.append("    none.")

    lines += [
        "",
        "  Repeated action items",
        "    The same commitment made in more than one review, which is evidence",
        "    the first attempt never landed.",
    ]
    if report.repeated_action_items:
        lines += [f'    - "{title}"' for title in report.repeated_action_items]
    else:
        lines.append("    none.")

    return "\n".join(lines)
