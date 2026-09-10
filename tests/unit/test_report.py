"""A halt moves the decision to a human. The report is the whole of what they get,
so anything summarised away is information they needed and no longer have.
"""

from ensemble.gate import evaluate_gate
from ensemble.report import format_halt_report
from ensemble.types import JudgeVerdict


def test_a_disagreement_report_carries_every_rater_position_verbatim(
    bands, make_rater, satisfied_judge
):
    result = evaluate_gate(
        [
            make_rater("claude", "meeting", "steady but narrow"),
            make_rater("gemini", "exceeding", "led the migration"),
        ],
        satisfied_judge,
        bands,
    )

    report = format_halt_report(result)

    for fragment in (
        "claude", "meeting", "steady but narrow",
        "gemini", "exceeding", "led the migration",
    ):
        assert fragment in report


def test_a_correlated_failure_report_carries_the_judge_objection_and_the_agreed_grade(
    bands, make_rater
):
    result = evaluate_gate(
        [
            make_rater("claude", "exceeding", "high ticket count"),
            make_rater("gemini", "exceeding", "high ticket count"),
        ],
        JudgeVerdict(justified=False, reasoning="ticket volume is not in the rubric"),
        bands,
    )

    report = format_halt_report(result)

    assert "ticket volume is not in the rubric" in report
    assert "exceeding" in report


def test_the_report_names_the_halt_condition(bands, make_rater, satisfied_judge):
    result = evaluate_gate(
        [make_rater("claude", "meeting"), make_rater("gemini", "exceeding")],
        satisfied_judge,
        bands,
    )

    assert "halt_disagreement" in format_halt_report(result).lower()


def test_a_long_rater_position_is_never_truncated(bands, make_rater, satisfied_judge):
    """Truncation is the failure mode that looks like tidiness."""
    long_reasoning = "the migration slipped twice " * 60

    result = evaluate_gate(
        [
            make_rater("claude", "meeting", long_reasoning),
            make_rater("gemini", "exceeding", "short"),
        ],
        satisfied_judge,
        bands,
    )

    assert long_reasoning in format_halt_report(result)
