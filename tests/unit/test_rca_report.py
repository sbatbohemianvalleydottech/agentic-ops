"""Rendering an incident review.

The first question an audit asks about an automated judgement is what produced
it. The ledger knows; the report is what people read.
"""

from rca_agent.judgement import DimensionGrade
from rca_agent.report import render_review
from rca_agent.structure import Review
from rca_agent.types import Dimension

MODELS = ("anthropic/claude-opus-5", "gemini/gemini-3.8-flash", "anthropic/claude-sonnet-5")

GRADES = [
    DimensionGrade(
        dimension=Dimension.CAUSE_NOT_TRIGGER,
        grade="weak",
        needs_human_review=False,
        reasoning="stops at the trigger",
    )
]


def test_an_assessed_report_names_the_rater_and_judge_models():
    report = render_review(Review(rca_id="rca-1"), GRADES, models=MODELS)

    for model in MODELS:
        assert model in report


def test_the_report_distinguishes_the_raters_from_the_judge():
    """"Assessed by X and Y" and "judged by Z" are different claims, and an
    audit needs to know which model was in which role."""
    report = render_review(Review(rca_id="rca-1"), GRADES, models=MODELS)

    assert "Assessed by" in report
    assert "judged by" in report


def test_a_deterministic_report_claims_no_models():
    """The offline path calls nothing, so naming a model would be a lie."""
    report = render_review(Review(rca_id="rca-1"))

    assert "Assessed by" not in report
    for model in MODELS:
        assert model not in report
