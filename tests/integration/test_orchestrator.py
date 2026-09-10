"""A full decision, end to end, against the fake provider. No network, no keys.

If any test in this file ever needs a credential, the gate has stopped being
auditable for free and something has gone wrong.
"""

import threading

from ensemble.gate import Decision
from ensemble.orchestrator import Rater, run_decision
from ensemble.providers.fake import FakeProvider


def decide(provider, bands, evidence, ledger, caller="test"):
    return run_decision(
        rubric=bands,
        evidence=evidence,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger,
        caller=caller,
    )


def test_a_unanimous_decision_proceeds(bands, evidence, ledger):
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "meeting"})

    result = decide(provider, bands, evidence, ledger)

    assert result.decision is Decision.PROCEED
    assert result.grade == "meeting"


def test_the_judge_is_called_even_when_raters_disagree(bands, evidence, ledger):
    """Judge independence has to be structural. Calling it only when raters agree
    would make its cost conditional on an outcome and hide regressions in the
    judge itself."""
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "exceeding"})

    result = decide(provider, bands, evidence, ledger)

    assert result.decision is Decision.HALT_DISAGREEMENT
    assert len(provider.judge_calls) == 1


def test_the_judge_never_receives_rater_output(bands, evidence, ledger):
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"},
        rater_reasoning="RATER_REASONING_MARKER",
    )

    decide(provider, bands, evidence, ledger)

    recorded = repr(provider.judge_calls)
    assert "RATER_REASONING_MARKER" not in recorded
    assert "model-a" not in recorded


def test_a_provider_error_yields_an_absent_verdict_rather_than_a_fabricated_one(
    bands, evidence, ledger
):
    """Returning a plausible default on failure is the exact thing this repository
    exists to prevent."""
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"},
        fail_models=frozenset({"model-b"}),
    )

    result = decide(provider, bands, evidence, ledger)

    assert result.decision is Decision.HALT_INCOMPLETE


def test_a_failed_call_carries_its_model_and_reason_into_the_result(
    bands, evidence, ledger
):
    """The first live run halted and blamed disagreement when every call had
    errored. The reason was known and discarded."""
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"},
        fail_models=frozenset({"model-b"}),
        fail_reason="BadRequestError: credit balance is too low",
    )

    result = decide(provider, bands, evidence, ledger)

    assert result.decision is Decision.HALT_INCOMPLETE
    failure = next(f for f in result.failures if f.model == "model-b")
    assert failure.role == "rater"
    assert "credit balance is too low" in failure.reason


def test_a_healthy_decision_records_no_failures(bands, evidence, ledger):
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "exceeding"})

    result = decide(provider, bands, evidence, ledger)

    assert result.decision is Decision.HALT_DISAGREEMENT
    assert result.failures == ()


def test_raters_are_invoked_concurrently(bands, evidence, ledger):
    """A barrier both raters must reach. If they run serially it times out."""
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"},
        barrier=threading.Barrier(2, timeout=5),
    )

    result = decide(provider, bands, evidence, ledger)

    assert result.decision is Decision.PROCEED


def test_one_ledger_record_is_written_per_model_call(
    bands, evidence, ledger, ledger_path
):
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "meeting"})

    result = decide(provider, bands, evidence, ledger, caller="perf-review")

    lines = ledger_path.read_text().strip().splitlines()
    assert len(lines) == 3  # two raters plus one judge
    assert result.decision is Decision.PROCEED
    assert ledger.cost_of(result.decision_id) > 0
