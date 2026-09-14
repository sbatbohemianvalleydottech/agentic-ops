"""Whether a document is worth paying to grade.

Separate from `structure.py` on purpose. A structural defect is a finding about
a review. This is a statement that the thing is not a review, and the two must
not be confused: `--fail-on-defects` gates on the first, and a document that was
never a post-incident review is not a failing build.

The three judgement dimensions read a stated cause, a narrative and the action
items. A document recording neither an analysis nor a commitment gives all three
nothing to work with, and two vendors plus a judge will return weak or contested
on every one of them, which the free structural pass established first and for
nothing.
"""

from __future__ import annotations

from .rubric import Rubric
from .types import RCA

# What each configurable field is called when a human reads it.
READS_AS = {
    "contributing_factors": "contributing factors",
    "action_items": "action items",
    "participants": "participants",
    "timeline": "a timeline",
    "stated_cause": "a stated cause",
    "narrative": "a narrative",
}


def below_bar(rca: RCA, rubric: Rubric) -> str | None:
    """Why this document is not worth judging, or None.

    Below the bar means every named field is empty. Any one of them present is
    enough: a review that committed to work gives the actions dimension
    something to read, and one that recorded an analysis gives the cause
    dimension something to read.
    """
    required = rubric.judgement_requires_any
    if not required:
        # An unset bar never fires. That is what a rubric copied before this
        # existed gets, and it is the safe direction: the old behaviour.
        return None

    if any(getattr(rca, field) for field in required):
        return None

    absent = " and no ".join(READS_AS.get(field, field) for field in required)
    return (
        f"not judged: this document records no {absent}. "
        "Grading the depth of an analysis that is not there would cost money "
        "and tell you what the structural pass above already has."
    )
