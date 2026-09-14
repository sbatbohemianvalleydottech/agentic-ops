"""Principle: every model call is metered. The probes were the exception.

Three probes run before every paid pass, one per configured model. They are
real calls to real vendors and they cost real money, and none of it reached
the ledger, so the ledger's own total was short by every probe ever run. Small
money, but the rule does not have a size threshold in it.
"""

import json
from decimal import Decimal

from ensemble.preflight import ModelCheck, preflight
from ledger import Ledger


def probe_for(costs):
    def probe(model):
        return ModelCheck(
            model=model,
            reachable=True,
            reason=None,
            cost=costs[model],
            input_tokens=11,
            output_tokens=2,
        )

    return probe


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_every_probe_reaches_the_ledger(tmp_path):
    path = tmp_path / "calls.jsonl"
    preflight(
        ["a/one", "b/two"],
        probe=probe_for({"a/one": 0.0002, "b/two": 0.0001}),
        ledger=Ledger(path),
        caller="test",
    )

    recorded = rows(path)
    assert [r["model"] for r in recorded] == ["a/one", "b/two"]
    assert {r["role"] for r in recorded} == {"probe"}
    assert {r["caller"] for r in recorded} == {"test"}


def test_the_probe_rows_carry_their_tokens(tmp_path):
    path = tmp_path / "calls.jsonl"
    preflight(["a/one"], probe=probe_for({"a/one": 0.0002}), ledger=Ledger(path))

    row = rows(path)[0]
    assert row["input_tokens"] == 11
    assert row["output_tokens"] == 2


def test_probe_spend_is_retrievable_as_its_own_total(tmp_path):
    path = tmp_path / "calls.jsonl"
    preflight(
        ["a/one", "b/two"],
        probe=probe_for({"a/one": 0.0002, "b/two": 0.0001}),
        ledger=Ledger(path),
    )

    assert Ledger(path).cost_of("preflight") == Decimal("0.0003")


def test_a_deduplicated_model_is_billed_and_recorded_once(tmp_path):
    """Probing is deduplicated. The ledger must not imply otherwise."""
    path = tmp_path / "calls.jsonl"
    preflight(
        ["a/one", "b/two", "a/one"],
        probe=probe_for({"a/one": 0.0002, "b/two": 0.0001}),
        ledger=Ledger(path),
    )

    assert len(rows(path)) == 2


def test_a_failed_probe_is_recorded_too(tmp_path):
    """A call that failed still happened. Principle covers it explicitly."""
    path = tmp_path / "calls.jsonl"

    def failing(model):
        return ModelCheck(model=model, reachable=False, reason="401", cost=0.0)

    preflight(["a/one"], probe=failing, ledger=Ledger(path))

    row = rows(path)[0]
    assert row["model"] == "a/one"
    assert row["cost"] == 0.0


def test_no_ledger_means_no_write_and_no_error(tmp_path):
    """The offline tests and the demo call this with nothing to write to."""
    result = preflight(["a/one"], probe=probe_for({"a/one": 0.0002}))
    assert result.ok
    assert list(tmp_path.iterdir()) == []
