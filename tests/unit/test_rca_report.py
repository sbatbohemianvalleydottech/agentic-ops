"""Rendering an incident review.

The first question an audit asks about an automated judgement is what produced
it. The ledger knows; the report is what people read.
"""

from ensemble.types import RaterVerdict
from rca_agent.judgement import DimensionGrade
from rca_agent.report import render_review
from rca_agent.structure import Review
from rca_agent.types import Dimension

MODELS = ("anthropic/claude-opus-5", "gemini/gemini-3.8-flash", "anthropic/claude-sonnet-5")


def flat(report: str) -> str:
    """The report wraps to a terminal width, so a sentence spans lines. Text is
    checked with whitespace normalised; that wrapping changes nothing else is
    asserted in test_wrap.py rather than assumed here."""
    return " ".join(report.split())

GRADES = [
    DimensionGrade(
        dimension=Dimension.CAUSE_NOT_TRIGGER,
        grade="weak",
        needs_human_review=False,
        reasoning="stops at the trigger",
        raters=(),
    )
]


OPUS = RaterVerdict(
    rater="anthropic/claude-opus-5",
    grade="weak",
    reasoning="Stops at the trigger. Nothing explains why a migration could take "
    "a table lock in business hours without a timeout. [rca-hollow:cause]",
)
GEMINI = RaterVerdict(
    rater="gemini/gemini-3.8-flash",
    grade="weak",
    reasoning="No account of the control that should have caught this before it "
    "reached production. [rca-hollow:narrative]",
)

GRADED = [
    DimensionGrade(
        dimension=Dimension.CAUSE_NOT_TRIGGER,
        grade="weak",
        needs_human_review=False,
        reasoning="",
        raters=(OPUS, GEMINI),
    )
]


def test_a_graded_dimension_shows_why_each_rater_graded_it_that_way():
    """The defect. Three live runs printed the word and binned several hundred
    tokens of paid-for explanation."""
    report = render_review(Review(rca_id="rca-1"), GRADED, models=MODELS)

    assert "Stops at the trigger" in flat(report)
    assert "control that should have caught this" in flat(report)


def test_each_reasoning_is_attributed_to_the_model_that_gave_it():
    report = render_review(Review(rca_id="rca-1"), GRADED, models=MODELS)

    text = flat(report)
    opus_at = text.index("anthropic/claude-opus-5", text.index("cause_not_trigger"))
    gemini_at = text.index("gemini/gemini-3.8-flash", text.index("cause_not_trigger"))

    assert text.index("Stops at the trigger") > opus_at
    assert text.index("control that should have caught this") > gemini_at


def test_two_raters_agreeing_do_not_have_their_reasons_merged():
    """Two raters returning weak is not two raters agreeing. Whether they got
    there by the same argument is the correlated-failure question, and merging
    the strings destroys the only place a human could see it."""
    report = render_review(Review(rca_id="rca-1"), GRADED, models=MODELS)

    assert "; ".join((OPUS.reasoning, GEMINI.reasoning)) not in flat(report)
    assert " ".join(OPUS.reasoning.split()) in flat(report)
    assert " ".join(GEMINI.reasoning.split()) in flat(report)


def test_a_contested_dimension_keeps_its_halt_explanation():
    contested = [
        DimensionGrade(
            dimension=Dimension.NO_ALTERNATE_REALITY,
            grade=None,
            needs_human_review=True,
            reasoning="Assessment halted. Assessors disagreed: a said adequate.",
            raters=(OPUS, GEMINI),
        )
    ]
    report = render_review(Review(rca_id="rca-1"), contested, models=MODELS)

    assert "Assessors disagreed" in flat(report)
    assert "Stops at the trigger" in flat(report)


def test_a_deterministic_report_claims_no_reasoning():
    report = render_review(Review(rca_id="rca-1"))

    assert "Stops at the trigger" not in flat(report)
    assert "Judgement dimensions" not in report


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
