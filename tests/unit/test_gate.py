from ensemble.gate import Decision, evaluate_gate
from ensemble.types import JudgeVerdict, RaterVerdict


def test_agreement_with_justified_judge_proceeds():
    raters = [
        RaterVerdict(rater="rater-a", grade="meeting", reasoning="shipped consistently"),
        RaterVerdict(rater="rater-b", grade="meeting", reasoning="steady delivery"),
    ]
    judge = JudgeVerdict(justified=True, reasoning="evidence supports the band")

    result = evaluate_gate(raters, judge)

    assert result.decision is Decision.PROCEED


def test_raters_disagreeing_halts_even_when_judge_is_satisfied():
    raters = [
        RaterVerdict(rater="rater-a", grade="meeting", reasoning="steady delivery"),
        RaterVerdict(rater="rater-b", grade="exceeding", reasoning="led the migration"),
    ]
    judge = JudgeVerdict(justified=True, reasoning="either band is arguable")

    result = evaluate_gate(raters, judge)

    assert result.decision is Decision.HALT_DISAGREEMENT


def test_unanimous_raters_still_halt_when_the_judge_rejects_the_grade():
    """Correlated failure: the case a simple grade comparison cannot catch."""
    raters = [
        RaterVerdict(rater="rater-a", grade="exceeding", reasoning="high ticket count"),
        RaterVerdict(rater="rater-b", grade="exceeding", reasoning="high ticket count"),
    ]
    judge = JudgeVerdict(
        justified=False,
        reasoning="ticket volume is not in the rubric; no cited evidence for impact",
    )

    result = evaluate_gate(raters, judge)

    assert result.decision is Decision.HALT_CORRELATED_FAILURE
