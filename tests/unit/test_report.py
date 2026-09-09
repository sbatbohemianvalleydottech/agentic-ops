"""A halt moves the decision to a human. The report is the whole of what they get,
so anything summarised away is information they needed and no longer have.
"""

from ensemble.gate import evaluate_gate
from ensemble.report import format_halt_report
from ensemble.types import JudgeVerdict, RaterVerdict, Rubric

BANDS = Rubric(
    name="performance",
    criteria="assess the year against the rubric",
    scale=("not meeting", "meeting", "exceeding"),
)


def test_a_disagreement_report_carries_every_rater_position_verbatim():
    result = evaluate_gate(
        [
            RaterVerdict(rater="claude", grade="meeting", reasoning="steady but narrow"),
            RaterVerdict(rater="gemini", grade="exceeding", reasoning="led the migration"),
        ],
        JudgeVerdict(justified=True, reasoning="either band is arguable"),
        BANDS,
    )

    report = format_halt_report(result)

    assert "claude" in report
    assert "meeting" in report
    assert "steady but narrow" in report
    assert "gemini" in report
    assert "exceeding" in report
    assert "led the migration" in report


def test_a_correlated_failure_report_carries_the_judge_objection_and_the_agreed_grade():
    result = evaluate_gate(
        [
            RaterVerdict(rater="claude", grade="exceeding", reasoning="high ticket count"),
            RaterVerdict(rater="gemini", grade="exceeding", reasoning="high ticket count"),
        ],
        JudgeVerdict(justified=False, reasoning="ticket volume is not in the rubric"),
        BANDS,
    )

    report = format_halt_report(result)

    assert "ticket volume is not in the rubric" in report
    assert "exceeding" in report


def test_the_report_names_the_halt_condition():
    result = evaluate_gate(
        [
            RaterVerdict(rater="claude", grade="meeting", reasoning="a"),
            RaterVerdict(rater="gemini", grade="exceeding", reasoning="b"),
        ],
        JudgeVerdict(justified=True, reasoning="c"),
        BANDS,
    )

    report = format_halt_report(result)

    assert "halt_disagreement" in report.lower()


def test_a_long_rater_position_is_never_truncated():
    """Truncation is the failure mode that looks like tidiness."""
    long_reasoning = "the migration slipped twice " * 60

    result = evaluate_gate(
        [
            RaterVerdict(rater="claude", grade="meeting", reasoning=long_reasoning),
            RaterVerdict(rater="gemini", grade="exceeding", reasoning="short"),
        ],
        JudgeVerdict(justified=True, reasoning="either is arguable"),
        BANDS,
    )

    report = format_halt_report(result)

    assert long_reasoning in report
