"""Whether a document is worth paying to grade.

The repository's own README says an incident review missing a detection
timestamp does not need a second opinion, and that paying for one would be the
tool failing to think. It then paid, on three status page entries that record no
contributing factor, no action item and no participant. Every dimension came
back weak or contested, which the free structural pass had already established
for nothing.

The bar is both absent, not either. A review with action items and no
contributing factors has committed to work, and the actions dimension has
something to read. A review with contributing factors and no action items has
recorded an analysis, and the cause dimension has something to read. Both
absent means the document records neither why it happened nor what anyone will
do, and the three judgement dimensions have nothing to read at all.

This is not a structural defect and it does not live with them. A defect is a
finding about a review. This is a statement that the thing is not one, and the
two must not be confused, because --fail-on-defects gates on the first.
"""

from dataclasses import replace

import pytest

from rca_agent.rubric import Rubric, load_rubric
from rca_agent.types import RCA, ActionItem, Category
from rca_agent.worth_judging import below_bar

BAR = ("contributing_factors", "action_items")


def review(*, factors=(), items=()) -> RCA:
    return RCA(
        rca_id="r-1",
        severity="sev2",
        timeline=(),
        impact="",
        stated_cause="",
        contributing_factors=tuple(factors),
        narrative="",
        participants=(),
        action_items=tuple(items),
    )


def an_item() -> ActionItem:
    return ActionItem(
        title="Add a guard",
        state="open",
        created=None,
        owner="Someone",
        due=None,
        tracker_ref="T-1",
        category=Category.PREVENT,
        closure_evidence=None,
    )


@pytest.fixture
def rubric():
    return replace(load_rubric(), judgement_requires_any=BAR)


def test_a_document_with_neither_is_below_the_bar(rubric):
    assert below_bar(review(), rubric) is not None


def test_the_reason_names_both_absences(rubric):
    """A refusal that does not say what was missing cannot be acted on."""
    reason = below_bar(review(), rubric)
    assert "contributing factors" in reason
    assert "action items" in reason


def test_contributing_factors_alone_clear_the_bar(rubric):
    assert below_bar(review(factors=("the alert was never wired",)), rubric) is None


def test_action_items_alone_clear_the_bar(rubric):
    assert below_bar(review(items=(an_item(),)), rubric) is None


def test_both_present_clears_the_bar(rubric):
    assert below_bar(review(factors=("a",), items=(an_item(),)), rubric) is None


def test_an_empty_setting_never_fires():
    """What a rubric copied before this existed gets: the old behaviour."""
    assert below_bar(review(), replace(load_rubric(), judgement_requires_any=())) is None


def test_the_shipped_rubric_has_the_bar_set():
    """Defaulting the dataclass to empty is for copied rubrics, not for ours."""
    assert load_rubric().judgement_requires_any == BAR


def test_an_unknown_field_name_is_an_error_at_load(tmp_path):
    """A typo would otherwise produce a bar that can never fire, which reads as
    a configured control and is not one."""
    path = tmp_path / "rubric.toml"
    path.write_text(
        "required_moments = []\n"
        "blame_phrases = []\n"
        "export_window_days = 7\n"
        'grade_scale = ["weak", "strong"]\n'
        "min_contributing_factors = 2\n"
        'judgement_requires_any = ["contributing_factrs"]\n'
    )
    with pytest.raises(ValueError, match="contributing_factrs"):
        load_rubric(path)


def test_every_named_field_is_one_an_rca_actually_has():
    """Guards the shipped setting against the same typo."""
    for field in load_rubric().judgement_requires_any:
        assert hasattr(review(), field)


def test_the_bar_is_not_a_structural_defect():
    """Separate question, separate module, separate report line. If this ever
    becomes a Defect, --fail-on-defects starts failing builds over documents
    that were never reviews."""
    from rca_agent.structure import check_structure

    rubric = load_rubric()
    defects = check_structure(review(), rubric, __import__("datetime").datetime(2026, 1, 1))
    assert all("not a review" not in defect.detail for defect in defects.defects)


def test_it_takes_a_rubric_rather_than_reading_the_default(rubric):
    """The bar is configuration. A function that reached for the shipped file
    could not be overruled by --rubric."""
    strict = replace(rubric, judgement_requires_any=("action_items",))
    assert below_bar(review(factors=("a",)), strict) is not None
    assert below_bar(review(factors=("a",)), rubric) is None


def test_the_rubric_type_still_constructs_without_the_setting():
    """Positionally, the way a copied rubric or an old test does."""
    old = Rubric(
        required_moments=(),
        blame_phrases=(),
        export_window_days=7,
        grade_scale=("weak", "strong"),
        min_contributing_factors=2,
    )
    assert below_bar(review(), old) is None
