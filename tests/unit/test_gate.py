"""The three outcomes that are the whole point of the gate."""

from ensemble.gate import Decision, evaluate_gate
from ensemble.types import JudgeVerdict


def test_agreement_with_justified_judge_proceeds(bands, make_rater, satisfied_judge):
    raters = [
        make_rater("rater-a", "meeting", "shipped consistently"),
        make_rater("rater-b", "meeting", "steady delivery"),
    ]

    result = evaluate_gate(raters, satisfied_judge, bands)

    assert result.decision is Decision.PROCEED
    assert result.grade == "meeting"


def test_raters_disagreeing_halts_even_when_judge_is_satisfied(
    bands, make_rater, satisfied_judge
):
    raters = [
        make_rater("rater-a", "meeting", "steady delivery"),
        make_rater("rater-b", "exceeding", "led the migration"),
    ]

    result = evaluate_gate(raters, satisfied_judge, bands)

    assert result.decision is Decision.HALT_DISAGREEMENT
    assert result.grade is None


def test_unanimous_raters_still_halt_when_the_judge_rejects_the_grade(bands, make_rater):
    """Correlated failure: the case a simple grade comparison cannot catch."""
    raters = [
        make_rater("rater-a", "exceeding", "high ticket count"),
        make_rater("rater-b", "exceeding", "high ticket count"),
    ]
    judge = JudgeVerdict(
        justified=False,
        reasoning="ticket volume is not in the rubric; no cited evidence for impact",
    )

    result = evaluate_gate(raters, judge, bands)

    assert result.decision is Decision.HALT_CORRELATED_FAILURE
    assert result.grade is None
