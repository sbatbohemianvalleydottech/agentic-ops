"""Edge cases from spec.md. Each one is a way the gate could quietly degrade
into a single-model decision, which is the thing Principle I exists to prevent.
"""

import pytest

from ensemble.gate import Decision, evaluate_gate
from ensemble.types import JudgeVerdict, RaterVerdict, Rubric

BANDS = Rubric(
    name="performance",
    criteria="assess the year against the rubric",
    scale=("not meeting", "meeting", "exceeding"),
)

SATISFIED = JudgeVerdict(justified=True, reasoning="evidence supports the band")


def rater(name: str, grade: str) -> RaterVerdict:
    return RaterVerdict(rater=name, grade=grade, reasoning="because")


def test_a_single_rater_is_rejected_rather_than_treated_as_unanimous():
    """A misconfiguration, not an outcome. Returning a halt would let a caller
    retry it into a one-model decision."""
    with pytest.raises(ValueError):
        evaluate_gate([rater("a", "meeting")], SATISFIED, BANDS)


def test_a_missing_rater_verdict_halts_and_is_never_read_as_agreement():
    result = evaluate_gate([rater("a", "meeting"), None], SATISFIED, BANDS)

    assert result.decision is Decision.HALT_INCOMPLETE


def test_a_missing_judge_verdict_halts_rather_than_defaulting_to_proceed():
    result = evaluate_gate([rater("a", "meeting"), rater("b", "meeting")], None, BANDS)

    assert result.decision is Decision.HALT_INCOMPLETE


def test_a_grade_outside_the_scale_is_distinct_from_a_disagreement():
    """A broken prompt and a genuine judgement split need different human responses."""
    result = evaluate_gate(
        [rater("a", "meeting"), rater("b", "outstanding")], SATISFIED, BANDS
    )

    assert result.decision is Decision.HALT_INVALID_VERDICT


def test_a_two_against_one_split_is_a_disagreement_and_no_majority_is_taken():
    result = evaluate_gate(
        [rater("a", "meeting"), rater("b", "meeting"), rater("c", "exceeding")],
        SATISFIED,
        BANDS,
    )

    assert result.decision is Decision.HALT_DISAGREEMENT


def test_precedence_puts_incompleteness_ahead_of_an_invalid_grade():
    """Both conditions hold. The order has to be a decision, not an accident."""
    result = evaluate_gate([None, rater("b", "outstanding")], SATISFIED, BANDS)

    assert result.decision is Decision.HALT_INCOMPLETE


def test_precedence_puts_an_invalid_grade_ahead_of_a_disagreement():
    result = evaluate_gate(
        [rater("a", "meeting"), rater("b", "outstanding")], SATISFIED, BANDS
    )

    assert result.decision is Decision.HALT_INVALID_VERDICT


def test_a_halt_carries_every_rater_position_for_the_human():
    result = evaluate_gate(
        [rater("a", "meeting"), rater("b", "exceeding")], SATISFIED, BANDS
    )

    assert len(result.raters) == 2
    assert result.judge is SATISFIED
    assert result.grade is None
