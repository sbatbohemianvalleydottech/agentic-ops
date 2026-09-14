"""A review with no follow-ups cannot breach a follow-up export policy.

Found by running this against published incident reports. A status page entry
is closed, names no follow-ups, and exports nothing, so it was reported under
"Follow-ups not in a tracker beyond the window after closure". There were no
follow-ups. The sentence is false about that review, and it points a reader at
a tracker hygiene problem when the actual problem is that nobody agreed to do
anything.

The tool already says that, and says it better: "this review produced no action
items at all. Either the incident was trivial or it was never really reviewed,
and no automated check can tell you which." Reporting both double counts one
absence and mislabels it.
"""

from datetime import datetime

import pytest

from rca_agent.completion import report_completion
from rca_agent.rubric import load_rubric
from rca_agent.types import RCA, ActionItem, Category

AS_OF = datetime(2026, 9, 14)
LONG_AGO = datetime(2026, 1, 1)


def review(rca_id: str, items: tuple[ActionItem, ...], exported=None) -> RCA:
    return RCA(
        rca_id=rca_id,
        severity="sev2",
        timeline=(),
        impact="",
        stated_cause="",
        contributing_factors=(),
        narrative="",
        participants=(),
        action_items=items,
        closed_at=LONG_AGO,
        followups_exported_at=exported,
    )


def an_item() -> ActionItem:
    return ActionItem(
        title="Do the thing",
        state="open",
        created=LONG_AGO,
        owner="Someone",
        due=None,
        tracker_ref="T-1",
        category=Category.PREVENT,
        closure_evidence=None,
    )


@pytest.fixture
def breaches():
    rubric = load_rubric()

    def _breaches(corpus):
        return report_completion(corpus, rubric, AS_OF).export_policy_breaches

    return _breaches


def test_a_review_with_no_followups_is_not_an_export_breach(breaches):
    assert breaches([review("nothing-agreed", ())]) == ()


def test_a_review_with_followups_and_no_export_still_breaches(breaches):
    """Unchanged. This is the case the check exists for."""
    assert breaches([review("agreed-but-untracked", (an_item(),))]) == (
        "agreed-but-untracked",
    )


def test_a_review_that_exported_does_not_breach(breaches):
    assert breaches([review("tidy", (an_item(),), exported=LONG_AGO)]) == ()


def test_the_two_cases_are_distinguished_in_one_corpus(breaches):
    """The whole point: only the one with something to export is named."""
    corpus = [review("nothing-agreed", ()), review("agreed-but-untracked", (an_item(),))]
    assert breaches(corpus) == ("agreed-but-untracked",)
