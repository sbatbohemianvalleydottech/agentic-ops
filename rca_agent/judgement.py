"""The dimensions that need judgement, each independently gated.

These are the three failures a structurally perfect RCA can still have. A
document can have all four timeline moments, quantified impact, blameless
language and a declared preventive action item, and still stop at the trigger,
still slide into what should have happened, and still promise a fix that fixes
nothing.

Each dimension gets its own gated decision. One overall grade would tell a
reviewer nothing about what to look at, and one contested judgement would halt
the entire review.
"""

from dataclasses import dataclass
from datetime import datetime

from ensemble.explain import explain
from ensemble.gate import Decision
from ensemble.orchestrator import Rater, run_decision
from ensemble.types import EvidenceBundle, EvidenceRecord, RaterVerdict
from ensemble.types import Rubric as GateRubric

from .rubric import Rubric
from .types import JUDGEMENT_DIMENSIONS, RCA, Dimension

CRITERIA = {
    Dimension.CAUSE_NOT_TRIGGER: (
        "Does the stated cause explain why this happened, or does it stop at what "
        "happened? 'A bad deploy went out' names the trigger; the cause is whatever "
        "let a bad deploy reach production undetected. Grade the depth of the "
        "explanation, not the quality of the writing."
    ),
    # Rewritten after it contested on every document in every run, on fixtures
    # and on published incident reports alike, while costing 1.7 to 2.0 times
    # the dimensions that reached a grade.
    #
    # The old wording asked whether the review kept what happened apart from
    # what should have happened. An assessor never sees the review as a
    # document: it sees the bundle below, whose records are already labelled and
    # already separated. The question was about a property the bundle removes
    # before anyone reads it, so it was answered from priors, and two sets of
    # priors gave two answers every time. The second fault was in the same
    # sentence: action items are prescriptive by design, and nothing said
    # whether they counted, so one reading graded weak and the other adequate
    # and both were defensible.
    Dimension.NO_ALTERNATE_REALITY: (
        "Read the record labelled Narrative, and only that record. Does it state "
        "what was observed and what was done, or does it carry statements about "
        "what should have happened or would have happened: 'we should have caught "
        "this', 'had the alert fired', 'the fix is to validate the config'? A "
        "narrative carrying the hypothetical fix means the actual sequence was "
        "never established. Ignore the action items entirely: those are supposed "
        "to say what will be done, and they are graded elsewhere."
    ),
    Dimension.ACTIONS_WOULD_PREVENT: (
        "Would the action items marked as preventive actually stop this recurring? "
        "An item can be well-formed, owned, dated and tracked and still not prevent "
        "anything. 'Review settings before deploys' asks people to be careful. Grade "
        "whether a mechanism changes."
    ),
}


@dataclass(frozen=True)
class DimensionGrade:
    dimension: Dimension
    grade: str | None
    needs_human_review: bool
    # On a halt, why the gate refused. Not the raters' reasoning: that is carried
    # separately and per model, because joining the two destroys the only place a
    # human can see two raters reaching one grade by different arguments.
    reasoning: str
    raters: tuple[RaterVerdict, ...] = ()


def _evidence(rca: RCA) -> EvidenceBundle:
    """Every field an assessor needs, each with a reference so any claim it makes
    can be traced back."""
    records = [
        EvidenceRecord(
            source="rca", timestamp=rca.closed_at or datetime.min,
            ref=f"{rca.rca_id}:cause", content=f"Stated cause: {rca.stated_cause}",
        ),
        EvidenceRecord(
            source="rca", timestamp=rca.closed_at or datetime.min,
            ref=f"{rca.rca_id}:impact", content=f"Impact: {rca.impact}",
        ),
        EvidenceRecord(
            source="rca", timestamp=rca.closed_at or datetime.min,
            ref=f"{rca.rca_id}:narrative", content=f"Narrative: {rca.narrative}",
        ),
    ]
    records += [
        EvidenceRecord(
            source="rca", timestamp=rca.closed_at or datetime.min,
            ref=f"{rca.rca_id}:factor-{index}", content=f"Contributing factor: {factor}",
        )
        for index, factor in enumerate(rca.contributing_factors)
    ]
    records += [
        EvidenceRecord(
            source="rca", timestamp=rca.closed_at or datetime.min,
            ref=f"{rca.rca_id}:action-{index}",
            content=(
                f"Action item ({item.category.value if item.category else 'uncategorised'}): "
                f"{item.title}"
            ),
        )
        for index, item in enumerate(rca.action_items)
    ]

    return EvidenceBundle(subject=f"incident review {rca.rca_id}", records=tuple(records))


def assess_judgement(
    rca: RCA,
    rubric: Rubric,
    *,
    raters: list[Rater],
    judge: Rater,
    ledger,
    progress=None,
) -> list[DimensionGrade]:
    evidence = _evidence(rca)
    grades = []

    for dimension in JUDGEMENT_DIMENSIONS:
        # Every dimension is assessed regardless of the structural result and
        # regardless of how the previous one went. Assessment conditional on an
        # outcome hides regressions, which is why feature 001 always calls the
        # judge.
        result = run_decision(
            rubric=GateRubric(
                name=dimension.value,
                criteria=CRITERIA[dimension],
                scale=rubric.grade_scale,
            ),
            evidence=evidence,
            raters=raters,
            judge=judge,
            ledger=ledger,
            caller=f"rca_agent:{rca.rca_id}",
            progress=progress,
        )

        halted = result.decision is not Decision.PROCEED

        # On a halt, why is `explain`'s job. The raters' own reasoning travels
        # separately, per model, so it survives to the report either way.
        reasoning = explain(result) if halted else ""

        grades.append(
            DimensionGrade(
                dimension=dimension,
                # No grade on a halt. A middle value here would be exactly the
                # fabricated agreement the gate exists to prevent.
                grade=None if halted else result.grade,
                needs_human_review=halted,
                reasoning=reasoning,
                # Kept whether or not the gate acted on them. Refusing to decide
                # on a verdict is not the same as the verdict being unfit to read.
                raters=result.raters,
            )
        )

    return grades
