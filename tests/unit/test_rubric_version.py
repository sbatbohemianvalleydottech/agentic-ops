"""A ledger row records which question was asked, not only which template.

`PROMPT_VERSION` fingerprints the adapter's two prompt templates. It does not
cover the criteria, which is the part that lives in a config file and is the
part anyone actually edits. So rewriting a dimension's criteria left every
ledger row claiming the same prompt_version as the runs before it, and a control
whose docstring says a verdict can be attributed to the wording that produced it
was attributing half of it.

Found while rewriting `no_alternate_reality`: the whole point of that change was
to compare runs before and against after, and the ledger said the two runs were
the same wording.

Two fields rather than one, because they are two facts. The template can change
while the criteria does not, and a criteria edit is a change somebody made to a
file they own.
"""

import pytest

from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric

pytest.importorskip("litellm")

import ensemble.providers.litellm as adapter  # noqa: E402
from ensemble.providers.litellm import PROMPT_VERSION, version_of  # noqa: E402

EVIDENCE = EvidenceBundle(
    subject="s",
    records=(
        EvidenceRecord(
            source="src",
            timestamp=__import__("datetime").datetime(2026, 1, 1),
            ref="ref",
            content="content",
        ),
    ),
)


def rubric(criteria: str) -> Rubric:
    return Rubric(name="r", criteria=criteria, scale=("weak", "strong"))


@pytest.fixture
def answering(monkeypatch):
    from tests.unit.test_providers import _Response

    monkeypatch.setattr(adapter, "completion", lambda **kwargs: _Response())
    monkeypatch.setattr(adapter, "supports_response_schema", lambda **kwargs: True)
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.001)


def test_a_rater_call_records_the_criteria_it_sent(answering):
    call = adapter.LiteLLMProvider().grade(rubric("ask this"), EVIDENCE, "some/model")
    assert call.rubric_version == version_of("ask this")


def test_a_judge_call_records_it_too(answering):
    call = adapter.LiteLLMProvider().judge(
        rubric("ask this"), EVIDENCE, "weak", "some/model"
    )
    assert call.rubric_version == version_of("ask this")


def test_two_different_criteria_produce_two_versions(answering):
    provider = adapter.LiteLLMProvider()
    first = provider.grade(rubric("ask this"), EVIDENCE, "some/model")
    second = provider.grade(rubric("ask that"), EVIDENCE, "some/model")
    assert first.rubric_version != second.rubric_version


def test_the_template_version_is_unaffected_by_the_criteria(answering):
    """Two facts, kept apart. Editing a criteria is not editing the adapter."""
    call = adapter.LiteLLMProvider().grade(rubric("anything"), EVIDENCE, "some/model")
    assert call.prompt_version == PROMPT_VERSION


def test_a_failed_call_still_records_which_question_was_asked(monkeypatch):
    """A halt is a claim too, and it is worth knowing what it halted on."""
    monkeypatch.setattr(
        adapter, "completion", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("down"))
    )
    monkeypatch.setattr(adapter, "supports_response_schema", lambda **kwargs: True)
    call = adapter.LiteLLMProvider().grade(rubric("ask this"), EVIDENCE, "some/model")
    assert call.failed
    assert call.rubric_version == version_of("ask this")


def test_it_reaches_the_ledger(tmp_path):
    """The field is worth nothing if it stops at the Call."""
    import json

    from ensemble.gate import Decision
    from ensemble.orchestrator import Rater, run_decision
    from ensemble.providers.fake import FakeProvider
    from ledger import Ledger

    provider = FakeProvider(grades={"a": "strong", "b": "strong"})
    ledger = Ledger(tmp_path / "calls.jsonl")
    result = run_decision(
        rubric=rubric("the question asked"),
        evidence=EVIDENCE,
        raters=[Rater(provider, "a"), Rater(provider, "b")],
        judge=Rater(provider, "j"),
        ledger=ledger,
        caller="test",
    )
    assert result.decision is Decision.PROCEED

    rows = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert rows
    assert all("rubric_version" in row for row in rows)
