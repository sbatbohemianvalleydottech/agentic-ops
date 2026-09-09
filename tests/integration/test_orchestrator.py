"""A full decision, end to end, against the fake provider. No network, no keys.

If any test in this file ever needs a credential, the gate has stopped being
auditable for free and something has gone wrong.
"""

import threading

from ensemble.gate import Decision
from ensemble.orchestrator import Rater, run_decision
from ensemble.providers.fake import FakeProvider
from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric
from ledger import Ledger

from datetime import datetime

BANDS = Rubric(
    name="performance",
    criteria="assess the year against the rubric",
    scale=("not meeting", "meeting", "exceeding"),
)

EVIDENCE = EvidenceBundle(
    subject="engineer-07",
    records=(
        EvidenceRecord(
            source="jira",
            timestamp=datetime(2026, 3, 1),
            ref="PLATFORM-412",
            content="closed the multi-region rollout",
        ),
    ),
)


def ledger_at(tmp_path) -> Ledger:
    return Ledger(tmp_path / "calls.jsonl")


def test_a_unanimous_decision_proceeds(tmp_path):
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "meeting"})

    result = run_decision(
        rubric=BANDS,
        evidence=EVIDENCE,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger_at(tmp_path),
        caller="test",
    )

    assert result.decision is Decision.PROCEED
    assert result.grade == "meeting"


def test_the_judge_is_called_even_when_raters_disagree(tmp_path):
    """Judge independence has to be structural. Calling it only when raters agree
    would make its cost conditional on an outcome and hide regressions in the
    judge itself."""
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "exceeding"})

    result = run_decision(
        rubric=BANDS,
        evidence=EVIDENCE,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger_at(tmp_path),
        caller="test",
    )

    assert result.decision is Decision.HALT_DISAGREEMENT
    assert len(provider.judge_calls) == 1


def test_the_judge_never_receives_rater_output(tmp_path):
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"},
        rater_reasoning="RATER_REASONING_MARKER",
    )

    run_decision(
        rubric=BANDS,
        evidence=EVIDENCE,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger_at(tmp_path),
        caller="test",
    )

    recorded = repr(provider.judge_calls)
    assert "RATER_REASONING_MARKER" not in recorded
    assert "model-a" not in recorded


def test_a_provider_error_yields_an_absent_verdict_rather_than_a_fabricated_one(tmp_path):
    """Returning a plausible default on failure is the exact thing this repository
    exists to prevent."""
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"},
        fail_models=frozenset({"model-b"}),
    )

    result = run_decision(
        rubric=BANDS,
        evidence=EVIDENCE,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger_at(tmp_path),
        caller="test",
    )

    assert result.decision is Decision.HALT_INCOMPLETE


def test_raters_are_invoked_concurrently(tmp_path):
    """A barrier both raters must reach. If they run serially it times out."""
    barrier = threading.Barrier(2, timeout=5)
    provider = FakeProvider(
        grades={"model-a": "meeting", "model-b": "meeting"}, barrier=barrier
    )

    result = run_decision(
        rubric=BANDS,
        evidence=EVIDENCE,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger_at(tmp_path),
        caller="test",
    )

    assert result.decision is Decision.PROCEED


def test_one_ledger_record_is_written_per_model_call(tmp_path):
    provider = FakeProvider(grades={"model-a": "meeting", "model-b": "meeting"})
    led = ledger_at(tmp_path)

    result = run_decision(
        rubric=BANDS,
        evidence=EVIDENCE,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=led,
        caller="perf-review",
    )

    lines = (tmp_path / "calls.jsonl").read_text().strip().splitlines()
    assert len(lines) == 3  # two raters plus one judge
    assert result.decision is Decision.PROCEED
    assert led.cost_of(result.decision_id) > 0
