"""What each dimension asks, and why one of them had to be rewritten.

`no_alternate_reality` contested in every run in every context, on fixtures and
on published incident reports alike, while costing 1.7 to 2.0 times the
dimensions that reached a grade. Two assessors disagreeing is the gate working.
Two assessors always disagreeing is a question that cannot be answered from what
they are given.

Two faults in one sentence. It asked whether the review "keeps the description
of what actually happened separate from what should have happened", and the
assessor never sees the review as a document: it sees an evidence bundle whose
records are already labelled and already separated, `Stated cause:`,
`Narrative:`, `Action item:`. The question was about a property the bundle
removed before anyone read it. And action items are prescriptive by design, so
an assessor counting them as "what should have happened" grades weak while one
excluding them grades adequate, and nothing in the wording said which.

These tests pin the properties the rewrite has to keep. They cannot show that it
discriminates, which needs a live run against the same documents; that result is
recorded in the README beside the claim it supports.
"""

import pytest

from rca_agent.judgement import CRITERIA
from rca_agent.types import JUDGEMENT_DIMENSIONS, Dimension

NAR = CRITERIA[Dimension.NO_ALTERNATE_REALITY]


def test_every_judged_dimension_has_criteria():
    for dimension in JUDGEMENT_DIMENSIONS:
        assert CRITERIA[dimension].strip()


def test_no_two_dimensions_ask_the_same_thing():
    """A cheap guard that was missing. Two identical criteria would produce two
    identical grades and read as corroboration."""
    texts = [CRITERIA[dimension] for dimension in JUDGEMENT_DIMENSIONS]
    assert len(set(texts)) == len(texts)


def test_the_alternate_reality_criteria_names_the_record_to_read():
    """The bundle labels its records. A question that does not say which one it
    is about leaves the assessor to choose, and two assessors choose
    differently."""
    assert "Narrative" in NAR


def test_it_settles_whether_action_items_count():
    """Half the ambiguity. They are prescriptive by design, so an assessor
    counting them grades weak and one excluding them grades adequate, and both
    readings were defensible."""
    assert "action item" in NAR.lower()


def test_it_no_longer_asks_whether_two_things_are_kept_apart():
    """The property the evidence bundle removes before the assessor sees it."""
    assert "kept apart" not in NAR.lower()
    assert "separate" not in NAR.lower()


def test_it_gives_the_assessor_something_to_look_for():
    """A question with no examples is answered from the reader's priors, which
    is exactly what two different priors did to this one."""
    assert any(phrase in NAR.lower() for phrase in ("should have", "would have"))


@pytest.mark.parametrize("dimension", list(JUDGEMENT_DIMENSIONS))
def test_no_criteria_names_a_grade_from_the_scale(dimension):
    """A criteria that suggests an answer is not a question. Guards every
    dimension, not only the rewritten one."""
    text = CRITERIA[dimension].lower()
    for grade in ("weak", "adequate", "strong"):
        assert f"grade it {grade}" not in text
