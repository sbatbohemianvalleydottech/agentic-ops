"""Deterministic defects. No models, no network, no cost.

An RCA missing a detection timestamp does not need a second opinion, and paying
for one would be the tool failing to think.
"""

from datetime import datetime

import pytest

from rca_agent.rubric import load_rubric
from rca_agent.structure import check_structure
from rca_agent.types import RCA, ActionItem, Category, Dimension, TimelineMoment

AS_OF = datetime(2026, 9, 1)


@pytest.fixture
def rubric():
    return load_rubric()


def moment(name, hour, minute=0):
    return TimelineMoment(name=name, at=datetime(2026, 3, 1, hour, minute))


def action(**overrides):
    base = dict(
        title="Set a lock timeout on migrations",
        state="closed",
        created=datetime(2026, 3, 2),
        owner="Rae Lindqvist",
        due=datetime(2026, 4, 1),
        tracker_ref="PLAT-2211",
        category=Category.PREVENT,
        closure_evidence="PR 4412",
    )
    return ActionItem(**{**base, **overrides})


@pytest.fixture
def make_rca():
    def _make(**overrides) -> RCA:
        base = dict(
            rca_id="rca-test",
            severity="sev2",
            timeline=(
                moment("detection", 9),
                moment("escalation", 9, 20),
                moment("mitigation", 9, 48),
                moment("resolution", 10, 30),
            ),
            impact="412 merchants saw errors for 78 minutes.",
            stated_cause="Migrations acquire table locks with no timeout.",
            contributing_factors=(
                "The tooling has no default lock timeout.",
                "Write saturation is not alerted on.",
            ),
            narrative="Rae Lindqvist rolled the migration back at 09:48.",
            participants=("Rae Lindqvist", "Sam Okafor"),
            action_items=(action(),),
            closed_at=datetime(2026, 3, 3),
            followups_exported_at=datetime(2026, 3, 4),
        )
        return RCA(**{**base, **overrides})

    return _make


def dimensions(review) -> set[Dimension]:
    return {defect.dimension for defect in review.defects}


def test_a_clean_rca_produces_no_defects(make_rca, rubric):
    review = check_structure(make_rca(), rubric, AS_OF)

    assert review.defects == ()
    assert review.requires_human_judgement is False


def test_a_missing_required_moment_is_a_defect_naming_it(make_rca, rubric):
    review = check_structure(
        make_rca(timeline=(moment("detection", 9), moment("resolution", 10))),
        rubric,
        AS_OF,
    )

    defect = next(
        d for d in review.defects if d.dimension is Dimension.TIMELINE_COMPLETENESS
    )
    assert "escalation" in defect.detail or "escalation" in defect.quote


def test_mitigation_before_detection_is_a_defect(make_rca, rubric):
    """Either the timeline was reconstructed from memory, or detection happened
    informally and was never recorded. Both are findings."""
    review = check_structure(
        make_rca(
            timeline=(
                moment("detection", 10, 40),
                moment("escalation", 10, 52),
                moment("mitigation", 10, 5),
                moment("resolution", 11, 30),
            )
        ),
        rubric,
        AS_OF,
    )

    assert Dimension.TIMELINE_COMPLETENESS in dimensions(review)


def test_impact_with_no_measured_quantity_is_a_defect(make_rca, rubric):
    review = check_structure(
        make_rca(impact="Some customers were affected for a while."), rubric, AS_OF
    )

    assert Dimension.IMPACT_QUANTIFIED in dimensions(review)


def test_a_blame_phrase_in_the_stated_cause_is_a_defect_quoting_it(make_rca, rubric):
    review = check_structure(
        make_rca(stated_cause="Human error. The engineer failed to check the config."),
        rubric,
        AS_OF,
    )

    defect = next(d for d in review.defects if d.dimension is Dimension.BLAMELESS)
    assert "human error" in defect.quote.lower()


def test_a_roster_name_in_a_cause_field_is_a_defect(make_rca, rubric):
    review = check_structure(
        make_rca(
            contributing_factors=(
                "Sam Okafor applied the wrong config.",
                "There is no validation in CI.",
            )
        ),
        rubric,
        AS_OF,
    )

    assert Dimension.BLAMELESS in dimensions(review)


def test_the_narrative_is_never_scanned_for_blame(make_rca, rubric):
    """A person belongs in the narrative. Flagging 'Rae rolled it back' would
    train people to ignore the check, so the check does not look there."""
    review = check_structure(
        make_rca(
            narrative=(
                "Sam Okafor failed to check the config and Rae Lindqvist forgot to "
                "page the database team. Human error throughout."
            )
        ),
        rubric,
        AS_OF,
    )

    assert Dimension.BLAMELESS not in dimensions(review)


def test_an_incomplete_action_item_yields_one_defect_per_missing_attribute(
    make_rca, rubric
):
    review = check_structure(
        make_rca(
            action_items=(
                action(owner=None, due=None, tracker_ref=None, category=None),
            )
        ),
        rubric,
        AS_OF,
    )

    incomplete = [
        d for d in review.defects if d.dimension is Dimension.ACTION_ITEM_COMPLETE
    ]
    assert len(incomplete) == 4


def test_action_items_that_only_improve_detection_report_no_preventive_action(
    make_rca, rubric
):
    """An RCA that only improves detection has accepted the recurrence."""
    review = check_structure(
        make_rca(
            action_items=(
                action(category=Category.PREPARE),
                action(category=Category.PREPARE, title="Add a dashboard panel"),
            )
        ),
        rubric,
        AS_OF,
    )

    assert Dimension.HAS_PREVENTIVE_ACTION in dimensions(review)


def test_an_rca_with_no_action_items_requires_human_judgement(make_rca, rubric):
    """Either trivial or never really reviewed, and which one it is needs a human."""
    review = check_structure(make_rca(action_items=()), rubric, AS_OF)

    assert review.requires_human_judgement is True


def test_too_few_contributing_factors_is_a_defect(make_rca, rubric):
    review = check_structure(
        make_rca(contributing_factors=("The tooling has no lock timeout.",)),
        rubric,
        AS_OF,
    )

    assert Dimension.CONTRIBUTING_FACTORS_PRESENT in dimensions(review)


def test_every_defect_carries_a_quote(make_rca, rubric):
    """SC-004: a disputed finding can be checked against the document without
    rerunning the tool."""
    review = check_structure(
        make_rca(
            impact="Some customers were affected.",
            stated_cause="Human error.",
            contributing_factors=(),
            timeline=(moment("detection", 9),),
            action_items=(action(owner=None, category=Category.PREPARE),),
        ),
        rubric,
        AS_OF,
    )

    assert review.defects
    for defect in review.defects:
        assert defect.quote.strip()
