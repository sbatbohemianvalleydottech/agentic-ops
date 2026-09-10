"""Explaining a halt.

Every halt in this repository is a claim about why nothing was decided, and
Principle II applies to that claim as much as to a grade. Two halts that look
alike are not alike: raters splitting and a judge rejecting an agreed grade have
different causes and different responses. The gate keeps them apart. Anything
that collapses them again undoes the gate in the only place a human reads.
"""

from ensemble.explain import explain
from ensemble.gate import Decision, GateResult
from ensemble.orchestrator import Failure
from ensemble.types import JudgeVerdict, RaterVerdict


def _result(decision, raters=(), judge=None, failures=()):
    return GateResult(
        decision=decision, raters=tuple(raters), judge=judge, failures=tuple(failures)
    )


SPLIT = (
    RaterVerdict(rater="anthropic/claude-opus-5", grade="weak", reasoning="stops short"),
    RaterVerdict(rater="gemini/gemini-3.8-flash", grade="strong", reasoning="reads fine"),
)


def test_a_disagreement_is_not_described_as_an_unsupported_grade():
    """The defect this feature exists for. A live run halted on disagreement and
    was explained as the judge rejecting an agreed grade, which sends the reader
    looking for a rejection that never happened."""
    text = explain(_result(Decision.HALT_DISAGREEMENT, raters=SPLIT))

    assert "disagree" in text.lower()
    assert "not supported" not in text.lower()
    assert "unsupported" not in text.lower()


def test_a_disagreement_shows_each_grade_next_to_its_model():
    """The split is the review. A human asked to adjudicate one without being
    shown it is redoing the work from nothing."""
    text = explain(_result(Decision.HALT_DISAGREEMENT, raters=SPLIT))

    assert "anthropic/claude-opus-5" in text
    assert "gemini/gemini-3.8-flash" in text
    assert "weak" in text
    assert "strong" in text


def test_a_correlated_failure_says_the_agreed_grade_was_not_supported():
    agreed = (
        RaterVerdict(rater="a", grade="strong", reasoning=""),
        RaterVerdict(rater="b", grade="strong", reasoning=""),
    )
    text = explain(
        _result(
            Decision.HALT_CORRELATED_FAILURE,
            raters=agreed,
            judge=JudgeVerdict(justified=False, reasoning="evidence does not show it"),
        )
    )

    assert "agreed" in text.lower()
    assert "disagree" not in text.lower()
    assert "strong" in text


def test_the_two_agreement_halts_do_not_read_alike():
    """They were one sentence. If they are still interchangeable the feature has
    not landed, whatever the individual assertions say."""
    disagreement = explain(_result(Decision.HALT_DISAGREEMENT, raters=SPLIT))
    correlated = explain(
        _result(
            Decision.HALT_CORRELATED_FAILURE,
            raters=(
                RaterVerdict(rater="a", grade="strong", reasoning=""),
                RaterVerdict(rater="b", grade="strong", reasoning=""),
            ),
            judge=JudgeVerdict(justified=False, reasoning="no"),
        )
    )

    assert disagreement != correlated


def test_an_invalid_verdict_names_the_grade_that_was_off_the_scale():
    off_scale = (
        RaterVerdict(rater="a", grade="excellent", reasoning=""),
        RaterVerdict(rater="b", grade="strong", reasoning=""),
    )
    text = explain(_result(Decision.HALT_INVALID_VERDICT, raters=off_scale))

    assert "excellent" in text


def test_call_failures_are_reported_and_no_grades_are_claimed():
    """A call that never returned cannot have disagreed. Saying otherwise sends
    the operator looking for a judgement problem that does not exist."""
    text = explain(
        _result(
            Decision.HALT_INCOMPLETE,
            failures=(
                Failure(model="gemini/gemini-3.8-flash", role="rater", reason="504"),
            ),
        )
    )

    assert "gemini/gemini-3.8-flash" in text
    assert "504" in text
    assert "disagree" not in text.lower()


def test_failures_are_explained_even_when_verdicts_also_disagree():
    """Failures take precedence. Whatever the surviving raters said, the run did
    not have the verdicts it needed."""
    text = explain(
        _result(
            Decision.HALT_DISAGREEMENT,
            raters=SPLIT,
            failures=(Failure(model="a", role="judge", reason="429 rate limited"),),
        )
    )

    assert "429 rate limited" in text


def test_proceed_is_not_explained_as_a_halt():
    text = explain(
        _result(
            Decision.PROCEED,
            raters=(
                RaterVerdict(rater="a", grade="strong", reasoning=""),
                RaterVerdict(rater="b", grade="strong", reasoning=""),
            ),
            judge=JudgeVerdict(justified=True, reasoning="yes"),
        )
    )

    assert "halt" not in text.lower()


def test_every_decision_has_its_own_explanation():
    """A halt kind added later must not be able to ship unexplained. That is the
    defect this feature fixes, one level up: the gap was never a wrong string, it
    was one string standing in for several outcomes."""
    texts = {}
    for decision in Decision:
        text = explain(_result(decision, raters=SPLIT))
        assert text.strip(), f"{decision.value} has no explanation"
        texts[decision] = text

    assert len(set(texts.values())) == len(Decision), (
        "two decisions share an explanation, which is the bug this feature fixes"
    )
