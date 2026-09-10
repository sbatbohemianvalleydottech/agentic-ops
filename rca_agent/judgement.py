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
from ensemble.types import EvidenceBundle, EvidenceRecord
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
    Dimension.NO_ALTERNATE_REALITY: (
        "Does this review keep the description of what actually happened separate "
        "from what should have happened? Slipping into the hypothetical fix while "
        "describing the incident means the actual sequence was never established. "
        "Grade whether the two are kept apart."
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
    reasoning: str


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

        # On a halt, why is `explain`'s job. It was built here once and in
        # cost_agent once, and both said "assessors did not agree this grade is
        # supported" for every halt kind, which describes correlated failure and
        # nothing else.
        reasoning = (
            "; ".join(v.reasoning for v in result.raters)
            if not halted
            else explain(result)
        )

        grades.append(
            DimensionGrade(
                dimension=dimension,
                # No grade on a halt. A middle value here would be exactly the
                # fabricated agreement the gate exists to prevent.
                grade=None if halted else result.grade,
                needs_human_review=halted,
                reasoning=reasoning,
            )
        )

    return grades
