"""Each fixture must fail the check it was built to fail, and only that one.

rca-hollow passing every structural check is the load-bearing assertion. If it
failed one, the deterministic layer would already have caught it and the
judgement layer would be proving nothing.
"""

from datetime import datetime
from pathlib import Path

import pytest

from rca_agent.completion import report_completion
from rca_agent.rubric import load_rubric
from rca_agent.structure import check_structure
from rca_agent.types import Dimension, load_corpus

CORPUS = Path(__file__).resolve().parents[2] / "rca_agent" / "fixtures" / "corpus"
AS_OF = datetime(2026, 9, 1)


@pytest.fixture(scope="module")
def reviews():
    rubric = load_rubric()
    return {
        rca.rca_id: check_structure(rca, rubric, AS_OF)
        for rca in load_corpus(CORPUS)
    }


def dimensions(review):
    return {defect.dimension for defect in review.defects}


def test_the_control_is_structurally_clean(reviews):
    assert reviews["rca-good"].defects == ()


def test_the_hollow_review_passes_every_structural_check(reviews):
    """The whole justification for the judgement layer. It is fluent, complete,
    and its stated cause is the trigger."""
    assert reviews["rca-hollow"].defects == ()
    assert reviews["rca-hollow"].requires_human_judgement is False


@pytest.mark.parametrize(
    "rca_id,expected",
    [
        ("rca-blame", Dimension.BLAMELESS),
        ("rca-detection-only", Dimension.HAS_PREVENTIVE_ACTION),
        ("rca-no-tickets", Dimension.ACTION_ITEM_COMPLETE),
        ("rca-broken-timeline", Dimension.TIMELINE_COMPLETENESS),
        ("rca-vague-impact", Dimension.IMPACT_QUANTIFIED),
    ],
)
def test_each_fixture_fails_the_check_it_was_built_to_fail(reviews, rca_id, expected):
    assert expected in dimensions(reviews[rca_id])


def test_the_blame_fixture_quotes_the_offending_sentence(reviews):
    defect = next(
        d for d in reviews["rca-blame"].defects if d.dimension is Dimension.BLAMELESS
    )

    assert defect.quote.strip()
    assert "human error" in defect.quote.lower() or "Tom Bergstrom" in defect.quote


def test_the_abandoned_review_is_structurally_fine_and_fails_on_completion(reviews):
    """Its problem is that nothing closed, which no single review surfaces."""
    assert reviews["rca-abandoned"].defects == ()

    report = report_completion(load_corpus(CORPUS), load_rubric(), AS_OF)
    assert "rca-abandoned" in report.export_policy_breaches


def test_the_corpus_surfaces_a_commitment_made_twice(reviews):
    """The lock timeout appears in rca-good and again in rca-abandoned. A repeated
    action item is evidence the first attempt never landed."""
    report = report_completion(load_corpus(CORPUS), load_rubric(), AS_OF)

    assert any("lock timeout" in title for title in report.repeated_action_items)
