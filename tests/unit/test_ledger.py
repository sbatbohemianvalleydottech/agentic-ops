"""What a decision cost has to survive the process that made it, or nobody can
answer the question afterwards.
"""

import json

import pytest

from ledger import Ledger


def test_one_record_is_appended_per_call(tmp_path):
    path = tmp_path / "calls.jsonl"
    led = Ledger(path)

    led.record(
        decision_id="d1", caller="perf-review", model="claude-opus-5",
        role="rater", input_tokens=1200, output_tokens=300, cost=0.0135,
    )
    led.record(
        decision_id="d1", caller="perf-review", model="gemini-2.5-pro",
        role="rater", input_tokens=1200, output_tokens=280, cost=0.0021,
    )

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["role"] == "rater"


def test_the_cost_of_one_decision_can_be_retrieved_afterwards(tmp_path):
    path = tmp_path / "calls.jsonl"
    led = Ledger(path)

    led.record(
        decision_id="d1", caller="perf-review", model="claude-opus-5",
        role="rater", input_tokens=1200, output_tokens=300, cost=0.0135,
    )
    led.record(
        decision_id="d1", caller="perf-review", model="claude-sonnet-5",
        role="judge", input_tokens=900, output_tokens=200, cost=0.0038,
    )
    led.record(
        decision_id="d2", caller="rca-agent", model="claude-opus-5",
        role="rater", input_tokens=400, output_tokens=100, cost=0.0045,
    )

    assert led.cost_of("d1") == pytest.approx(0.0173)
    assert led.cost_of("d2") == pytest.approx(0.0045)


def test_an_unknown_reader_tolerates_fields_it_does_not_recognise(tmp_path):
    """The record has to be able to grow without breaking existing consumers."""
    path = tmp_path / "calls.jsonl"
    path.write_text(
        json.dumps(
            {"decision_id": "d1", "cost": 0.01, "some_future_field": "whatever"}
        )
        + "\n"
    )

    assert Ledger(path).cost_of("d1") == pytest.approx(0.01)
