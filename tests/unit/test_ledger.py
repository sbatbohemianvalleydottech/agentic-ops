"""What a decision cost has to survive the process that made it, or nobody can
answer the question afterwards.
"""

import json
from decimal import Decimal

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

    assert led.cost_of("d1") == Decimal("0.0173")
    assert led.cost_of("d2") == Decimal("0.0045")


def test_a_record_says_which_rubric_the_decision_assessed(tmp_path):
    """"What a decision cost" is unanswerable per dimension without it. Three
    dimensions of one document produce three decisions, and nothing in the row
    said which was which, so the only way to tell them apart was row order.
    """
    path = tmp_path / "calls.jsonl"
    led = Ledger(path)

    led.record(
        decision_id="d1", caller="rca_agent:rca-hollow", model="claude-opus-5",
        role="rater", input_tokens=858, output_tokens=1017, cost=0.0297,
        rubric="no_alternate_reality",
    )

    assert json.loads(path.read_text())["rubric"] == "no_alternate_reality"


def test_the_rubric_is_optional_so_older_rows_still_parse(tmp_path):
    """Append-only means rows written before this field exists are permanent."""
    path = tmp_path / "calls.jsonl"
    Ledger(path).record(
        decision_id="d1", caller="c", model="m", role="rater",
        input_tokens=1, output_tokens=1, cost=0.01,
    )

    assert json.loads(path.read_text())["rubric"] is None
    assert Ledger(path).cost_of("d1") == Decimal("0.01")


def test_an_unknown_reader_tolerates_fields_it_does_not_recognise(tmp_path):
    """The record has to be able to grow without breaking existing consumers."""
    path = tmp_path / "calls.jsonl"
    path.write_text(
        json.dumps(
            {"decision_id": "d1", "cost": 0.01, "some_future_field": "whatever"}
        )
        + "\n"
    )

    assert Ledger(path).cost_of("d1") == Decimal("0.01")
