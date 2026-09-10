from dataclasses import dataclass
from enum import Enum

from .types import JudgeVerdict, RaterVerdict, Rubric


class Decision(Enum):
    PROCEED = "proceed"
    HALT_DISAGREEMENT = "halt_disagreement"
    HALT_CORRELATED_FAILURE = "halt_correlated_failure"
    HALT_INVALID_VERDICT = "halt_invalid_verdict"
    HALT_INCOMPLETE = "halt_incomplete"


@dataclass(frozen=True)
class GateResult:
    decision: Decision
    raters: tuple[RaterVerdict, ...]
    judge: JudgeVerdict | None
    grade: str | None = None
    # Set by the orchestrator, never by the gate. Keeping id generation out of
    # evaluate_gate is what lets it stay pure and deterministic.
    decision_id: str | None = None
    # Calls that produced no verdict, and why. Empty on a pure disagreement, so
    # a report can tell "they disagreed" apart from "nothing answered".
    failures: tuple = ()


def evaluate_gate(
    raters: list[RaterVerdict | None],
    judge: JudgeVerdict | None,
    rubric: Rubric,
) -> GateResult:
    """Decide whether a graded judgement may be acted on.

    Pure: no clock, no network, no I/O. The same verdicts always give the same
    outcome, which is what lets Principle I be audited by reading this function
    rather than trusted.

    Precedence is fixed because several conditions can hold at once, and which
    one a human is told about changes what they do next. See
    specs/001-ensemble-halt-gate/data-model.md.

    Raises:
        ValueError: fewer than two rater slots. That is a misconfiguration, not
            an outcome, and must not be reportable as a halt a caller could
            retry into a single-model decision.
    """
    if len(raters) < 2:
        raise ValueError(
            f"a gated decision needs at least two raters, got {len(raters)}; "
            "one rater cannot disagree with itself"
        )

    present = tuple(verdict for verdict in raters if verdict is not None)

    def halt(decision: Decision) -> GateResult:
        return GateResult(decision=decision, raters=present, judge=judge)

    # Absence is never agreement. Checked first, because every rule below would
    # otherwise read a partial ensemble as a healthy one.
    if len(present) < len(raters) or judge is None:
        return halt(Decision.HALT_INCOMPLETE)

    # A grade off the scale is a broken prompt or a changed provider, not a
    # judgement call, and it needs a different human response.
    if any(verdict.grade not in rubric.scale for verdict in present):
        return halt(Decision.HALT_INVALID_VERDICT)

    grades = {verdict.grade for verdict in present}
    if len(grades) > 1:
        # Any split, including two against one. No majority is taken.
        return halt(Decision.HALT_DISAGREEMENT)

    if not judge.justified:
        # Unanimous and wrong. The case a comparison cannot see.
        return halt(Decision.HALT_CORRELATED_FAILURE)

    return GateResult(
        decision=Decision.PROCEED,
        raters=present,
        judge=judge,
        grade=grades.pop(),
    )
