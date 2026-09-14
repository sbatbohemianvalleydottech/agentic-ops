"""The provider seam.

A failure has to carry its reason. A halt is a claim, and Principle II applies to
claims about why nothing came back just as much as to claims about a grade.
"""

import pytest

from ensemble.providers import Call, Usage, redact


def test_a_call_carries_a_verdict_usage_and_no_error_by_default():
    call = Call(verdict="anything", usage=Usage(1, 2, 0.5))

    assert call.error is None
    assert call.failed is False


def test_a_call_with_no_verdict_and_a_reason_is_a_failure():
    call = Call(verdict=None, usage=Usage(), error="BadRequestError: nope")

    assert call.failed is True


@pytest.mark.parametrize(
    "raw",
    [
        "auth failed for key sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH",
        'header {"x-goog-api-key": "AQ.Ab8RN6JabcdefghijKLMNOPqrstuvwx"}',
        "Bearer sk-proj-ZZZZYYYYXXXXWWWWVVVVUUUU",
    ],
)
def test_a_credential_never_survives_redaction(raw):
    """Provider messages are shown to the operator, so anything key-shaped is
    removed defensively rather than on evidence that it leaks."""
    cleaned = redact(raw)

    assert "sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHH" not in cleaned
    assert "AQ.Ab8RN6JabcdefghijKLMNOPqrstuvwx" not in cleaned
    assert "sk-proj-ZZZZYYYYXXXXWWWWVVVVUUUU" not in cleaned
    assert "REDACTED" in cleaned


def test_redaction_leaves_the_useful_part_of_a_message():
    message = (
        "BadRequestError: This API key is not scoped to a workspace, so this "
        "request must include the anthropic-workspace-id header."
    )

    assert redact(message) == message


def test_prompts_put_the_stable_evidence_before_the_varying_criteria():
    """Not caching. Removing the reason caching cannot be switched on later.

    The evidence is identical across every dimension and every rater; the
    criteria change per dimension. Stable content has to physically precede
    volatile content or a cache breakpoint has no prefix to sit on. No
    cache_control is set: at 308 evidence tokens we are under the 512-token
    minimum on Opus 5 and a marker would silently do nothing.
    """
    pytest.importorskip("litellm")
    from ensemble.providers.litellm import _JUDGE_PROMPT, _RATER_PROMPT

    for prompt in (_RATER_PROMPT, _JUDGE_PROMPT):
        assert prompt.index("{evidence}") < prompt.index("{criteria}")

    assert "cache_control" not in _RATER_PROMPT


class _Response:
    """Minimal stand-in for a litellm response."""

    class _Choice:
        class _Message:
            content = '{"grade": "strong", "reasoning": "because"}'

        message = _Message()

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5

    choices = [_Choice()]
    usage = _Usage()


def test_a_pricing_failure_does_not_discard_a_good_verdict(monkeypatch):
    """A model that answers correctly but has no published price must not be
    converted into a halt. That is fabrication in the opposite direction."""
    pytest.importorskip("litellm")
    import ensemble.providers.litellm as adapter

    monkeypatch.setattr(adapter, "completion", lambda **kwargs: _Response())
    monkeypatch.setattr(adapter, "supports_response_schema", lambda **kwargs: True)
    # The seam is the shared cost helper now, not a symbol on this adapter.
    monkeypatch.setattr(
        "ensemble.providers._recompute",
        lambda response: (_ for _ in ()).throw(RuntimeError("model not in map")),
    )

    call = adapter.LiteLLMProvider().grade(_rubric(), _evidence(), "some/model")

    assert call.failed is False
    assert call.verdict.grade == "strong"
    assert call.usage.cost == 0.0


def test_the_workspace_header_is_sent_only_when_configured(monkeypatch):
    pytest.importorskip("litellm")
    import ensemble.providers.litellm as adapter

    seen = {}

    def fake_completion(**kwargs):
        seen.clear()
        seen.update(kwargs)
        return _Response()

    monkeypatch.setattr(adapter, "completion", fake_completion)
    monkeypatch.setattr(adapter, "supports_response_schema", lambda **kwargs: True)
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.001)

    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    adapter.LiteLLMProvider().grade(_rubric(), _evidence(), "anthropic/x")
    assert "extra_headers" not in seen

    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_123")
    adapter.LiteLLMProvider().grade(_rubric(), _evidence(), "anthropic/x")
    assert seen["extra_headers"]["anthropic-workspace-id"] == "wrkspc_123"


def _rubric():
    from ensemble.types import Rubric

    return Rubric(name="r", criteria="c", scale=("weak", "strong"))


def _evidence():
    from datetime import datetime

    from ensemble.types import EvidenceBundle, EvidenceRecord

    return EvidenceBundle(
        subject="s",
        records=(
            EvidenceRecord(
                source="x", timestamp=datetime(2026, 1, 1), ref="r-1", content="c"
            ),
        ),
    )
