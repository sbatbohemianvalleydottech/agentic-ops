"""A phrase like "failed to" is only blame when a person is its subject.

Found by running this against real published incident reports rather than the
fixtures. GitHub's write-up of a Copilot review outage says:

    "Affected pull request reviews failed to complete or post review comments."

The check flagged it as attributing the failure to a person. Nobody is being
blamed there; a subsystem failed, which is ordinary incident English. The very
first real document put through it produced a false positive on the very check
the rubric exists to make trustworthy.

This matters more than a stray finding. The whole argument for reading only the
cause fields, and never the narrative, is that a check which misfires trains
people to ignore it, and then it catches nothing at all. A rule that fires on
every "the job failed to start" is that same failure arriving by a different
road.

So the phrases now come in two kinds. "Human error" blames a person on its own.
"Failed to" does not, and only counts when a person is in the same sentence:
someone on the participant roster, or one of the generic human subjects the
rubric lists.
"""

import pytest

from rca_agent.rubric import load_rubric
from rca_agent.structure import check_structure
from rca_agent.types import RCA, Dimension


def review(cause: str, participants: tuple[str, ...] = ()) -> RCA:
    return RCA(
        rca_id="r",
        severity="sev2",
        timeline=(),
        impact="",
        stated_cause=cause,
        contributing_factors=(),
        narrative="",
        participants=participants,
        action_items=(),
    )


@pytest.fixture
def blame_defects(as_of):
    rubric = load_rubric()

    def _defects(rca: RCA):
        return [
            d
            for d in check_structure(rca, rubric, as_of).defects
            if d.dimension is Dimension.BLAMELESS
        ]

    return _defects


# The real sentence that exposed this, and its shape.
SYSTEMS = [
    "Affected pull request reviews failed to complete or post review comments.",
    "The scheduled job failed to start after the config change.",
    "Replicas did not follow the new topology until restarted.",
    "The migration neglected to take the lock, so writes queued.",
]


@pytest.mark.parametrize("cause", SYSTEMS)
def test_a_system_failing_is_not_blame(blame_defects, cause):
    assert blame_defects(review(cause)) == []


PEOPLE = [
    ("The engineer failed to check the config before applying it.", ()),
    ("The operator forgot to drain the node first.", ()),
    ("The on-call did not follow the change checklist.", ()),
    ("Sam Okafor failed to check the config.", ("Sam Okafor",)),
]


@pytest.mark.parametrize("cause,participants", PEOPLE)
def test_a_person_failing_is_blame(blame_defects, cause, participants):
    assert blame_defects(review(cause, participants)) != []


STANDALONE = ["Human error.", "Operator error during the deploy.", "User error."]


@pytest.mark.parametrize("cause", STANDALONE)
def test_the_self_contained_phrases_still_fire_alone(blame_defects, cause):
    """"Human error" names a person by construction. It needs no subject."""
    assert blame_defects(review(cause)) != []


def test_a_named_participant_is_still_blame_on_its_own(blame_defects):
    """Unchanged behaviour: a person named in a cause field is blame regardless."""
    assert blame_defects(review("Tom Bergstrom approved it.", ("Tom Bergstrom",))) != []


def test_the_subject_must_be_in_the_same_sentence(blame_defects):
    """Otherwise any review mentioning an engineer anywhere trips every phrase."""
    cause = (
        "The engineer was paged at 02:10. The replication job failed to catch up "
        "before the window closed."
    )
    assert blame_defects(review(cause)) == []
