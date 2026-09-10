"""Why nothing was decided, in words that match what happened.

A halt is a claim, so Principle II applies to it. Two halts that look alike are
not alike: raters splitting and a judge rejecting an agreed grade have different
causes and call for different responses. The gate keeps them apart. This keeps
them apart in the sentence a human actually reads, which is the only place the
distinction pays for itself.

This lives beside the gate rather than in either agent because both agents built
this sentence independently and both got it wrong in identical words. Fixing it
twice would leave the mechanism that produced the bug in place.
"""

import textwrap

from .gate import Decision, GateResult


def wrap(text: str, *, indent: int, width: int = 78) -> list[str]:
    """Model prose, laid out without being rewritten.

    Whitespace is normalised and nothing else is. A wrapper that quietly edited
    what a model said would be a subtler version of the bug this module's
    feature exists to fix: a report showing something other than the evidence it
    claims to be showing.

    Empty reasoning is rendered as explicitly empty. A model that graded without
    explaining itself is a fact about the run, not an absence to tidy away.
    """
    pad = " " * indent
    collapsed = " ".join(text.split())
    if not collapsed:
        return [f"{pad}(no reasoning returned)"]
    return textwrap.wrap(collapsed, width=width, initial_indent=pad, subsequent_indent=pad)


def _said(result: GateResult) -> str:
    return ", ".join(f"{v.rater} said {v.grade}" for v in result.raters)


def _agreed(result: GateResult) -> str:
    grades = {v.grade for v in result.raters}
    return grades.pop() if len(grades) == 1 else "the proposed grade"


def explain(result: GateResult) -> str:
    """One sentence or two, true of this decision and no other."""
    if result.failures:
        # Precedence, not preference. A call that never returned cannot have
        # disagreed, and describing it as a judgement problem sends the operator
        # looking for one that does not exist.
        detail = "; ".join(
            f"{f.role} {f.model} failed: {f.reason}" for f in result.failures
        )
        return (
            f"Assessment halted before a judgement was possible: {detail}. "
            "No grade is claimed, because none came back."
        )

    if result.decision is Decision.PROCEED:
        grade = result.grade or _agreed(result)
        return f"Assessors agreed on {grade} and the judge found that justified."

    if result.decision is Decision.HALT_DISAGREEMENT:
        # The split is the review. Handing a human the adjudication without the
        # grades makes them redo the work from nothing.
        return (
            f"Assessment halted. Assessors disagreed: {_said(result)}. Nothing is "
            "averaged or settled by majority, so this one is a human's call."
        )

    if result.decision is Decision.HALT_CORRELATED_FAILURE:
        return (
            f"Assessment halted. Assessors agreed on {_agreed(result)} and the "
            "judge found that agreement was not borne out by the evidence. Models "
            "sharing a training lineage fail in the same direction, so agreement "
            "on its own is not confirmation."
        )

    if result.decision is Decision.HALT_INVALID_VERDICT:
        return (
            "Assessment halted. A grade came back that is not on this rubric's "
            f"scale. Assessors returned: {_said(result)}."
        )

    return (
        "Assessment halted. A verdict was missing and no failure was recorded, "
        "so there was nothing to judge."
    )
