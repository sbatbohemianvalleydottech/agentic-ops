"""Edge cases from spec.md. Each one is a way the gate could quietly degrade
into a single-model decision, which is the thing Principle I exists to prevent.
"""

import pytest

from ensemble.gate import Decision, evaluate_gate


def test_a_single_rater_is_rejected_rather_than_treated_as_unanimous(
    bands, make_rater, satisfied_judge
):
    """A misconfiguration, not an outcome. Returning a halt would let a caller
    retry it into a one-model decision."""
    with pytest.raises(ValueError):
        evaluate_gate([make_rater("a", "meeting")], satisfied_judge, bands)


def test_a_missing_rater_verdict_halts_and_is_never_read_as_agreement(
    bands, make_rater, satisfied_judge
):
    result = evaluate_gate([make_rater("a", "meeting"), None], satisfied_judge, bands)

    assert result.decision is Decision.HALT_INCOMPLETE


def test_a_missing_judge_verdict_halts_rather_than_defaulting_to_proceed(
    bands, make_rater
):
    result = evaluate_gate(
        [make_rater("a", "meeting"), make_rater("b", "meeting")], None, bands
    )

    assert result.decision is Decision.HALT_INCOMPLETE


def test_a_grade_outside_the_scale_is_distinct_from_a_disagreement(
    bands, make_rater, satisfied_judge
):
    """A broken prompt and a genuine judgement split need different human responses."""
    result = evaluate_gate(
        [make_rater("a", "meeting"), make_rater("b", "outstanding")],
        satisfied_judge,
        bands,
    )

    assert result.decision is Decision.HALT_INVALID_VERDICT


def test_a_two_against_one_split_is_a_disagreement_and_no_majority_is_taken(
    bands, make_rater, satisfied_judge
):
    result = evaluate_gate(
        [
            make_rater("a", "meeting"),
            make_rater("b", "meeting"),
            make_rater("c", "exceeding"),
        ],
        satisfied_judge,
        bands,
    )

    assert result.decision is Decision.HALT_DISAGREEMENT


def test_precedence_puts_incompleteness_ahead_of_an_invalid_grade(
    bands, make_rater, satisfied_judge
):
    """Both conditions hold. The order has to be a decision, not an accident."""
    result = evaluate_gate([None, make_rater("b", "outstanding")], satisfied_judge, bands)

    assert result.decision is Decision.HALT_INCOMPLETE


def test_precedence_puts_an_invalid_grade_ahead_of_a_disagreement(
    bands, make_rater, satisfied_judge
):
    result = evaluate_gate(
        [make_rater("a", "meeting"), make_rater("b", "outstanding")],
        satisfied_judge,
        bands,
    )

    assert result.decision is Decision.HALT_INVALID_VERDICT


def test_a_halt_carries_every_rater_position_for_the_human(
    bands, make_rater, satisfied_judge
):
    result = evaluate_gate(
        [make_rater("a", "meeting"), make_rater("b", "exceeding")],
        satisfied_judge,
        bands,
    )

    assert len(result.raters) == 2
    assert result.judge is satisfied_judge
    assert result.grade is None
