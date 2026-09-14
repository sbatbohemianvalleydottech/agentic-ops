"""A row in the ledger must be able to say what produced it.

Two independent runs of the same fixture on 14 September split on the same 3 of
4 drivers and gave different grades inside them. There was no way to tell
whether that was the models reading the rubric differently or the sampler, and
no way at all to tell a prompt change from either, because the prompts were
unversioned constants and nothing recorded which one a verdict came from.

Sampling is now pinned rather than left at whatever each vendor defaults to,
and every ledger row carries the version of the prompt set that produced it.
Neither makes the models agree. Both make a later claim about drift checkable
instead of a story.
"""

import json

import pytest

from ensemble.providers import Call, Usage
from ensemble.providers.fake import FakeProvider
from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric
from ledger import Ledger


def _rubric():
    return Rubric(name="r", criteria="c", scale=("weak", "strong"))


def _evidence():
    from datetime import UTC, datetime

    return EvidenceBundle(
        subject="s",
        records=(
            EvidenceRecord(
                source="src", timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                ref="ref", content="content",
            ),
        ),
    )


def test_a_call_carries_no_prompt_version_by_default():
    """Absent rather than a lie. An empty string is "nobody said"."""
    assert Call(verdict="x", usage=Usage()).prompt_version == ""


def test_the_fake_provider_stamps_itself():
    """A row produced offline must never be mistaken for a row from a vendor."""
    provider = FakeProvider(grades={"m": "strong"})
    call = provider.grade(_rubric(), _evidence(), "m")

    assert call.prompt_version == "fake"


def test_the_ledger_records_the_prompt_version(tmp_path):
    path = tmp_path / "calls.jsonl"
    Ledger(path).record(
        decision_id="d1", caller="test", model="m", role="rater",
        input_tokens=1, output_tokens=1, cost=0.01, prompt_version="7",
    )

    row = json.loads(path.read_text().splitlines()[0])
    assert row["prompt_version"] == "7"


def test_an_older_row_without_the_field_still_parses(tmp_path):
    """The field is new. Rows written before it exists must stay readable."""
    path = tmp_path / "calls.jsonl"
    Ledger(path).record(
        decision_id="d1", caller="test", model="m", role="rater",
        input_tokens=1, output_tokens=1, cost=0.01,
    )

    row = json.loads(path.read_text().splitlines()[0])
    assert row["prompt_version"] is None


def test_the_adapter_declares_a_prompt_version():
    pytest.importorskip("litellm")
    import ensemble.providers.litellm as adapter

    assert adapter.PROMPT_VERSION
    assert isinstance(adapter.PROMPT_VERSION, str)


def test_no_sampling_parameter_is_declared():
    """We tried. Neither vendor permits it, so nothing pretends otherwise."""
    pytest.importorskip("litellm")
    import ensemble.providers.litellm as adapter

    assert not hasattr(adapter, "TEMPERATURE")


@pytest.mark.parametrize("call_it", ["grade", "judge"])
def test_no_request_sends_a_sampling_parameter(monkeypatch, call_it):
    """A regression guard, because adding temperature back looks like a fix.

    On 14 September temperature=0.0 made every Anthropic call fail with
    UnsupportedParamsError, and the run cost $0.0137 producing four halts and
    no grades. The models do not accept it.
    """
    pytest.importorskip("litellm")
    import ensemble.providers.litellm as adapter
    from tests.unit.test_providers import _Response

    seen = {}

    def fake_completion(**kwargs):
        seen.clear()
        seen.update(kwargs)
        return _Response()

    monkeypatch.setattr(adapter, "completion", fake_completion)
    monkeypatch.setattr(adapter, "supports_response_schema", lambda **kwargs: True)
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.001)

    provider = adapter.LiteLLMProvider()
    if call_it == "grade":
        call = provider.grade(_rubric(), _evidence(), "some/model")
    else:
        call = provider.judge(_rubric(), _evidence(), "strong", "some/model")

    assert "temperature" not in seen
    assert "top_p" not in seen
    assert "top_k" not in seen
    assert call.prompt_version == adapter.PROMPT_VERSION
