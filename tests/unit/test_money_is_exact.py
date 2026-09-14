"""Money is summed exactly, everywhere it is summed.

The cost analyser has used Decimal end to end since the beginning, on the
argument that a reader who spots 100.0001% has reason to distrust everything
else. The three places that add up what a model call cost did not: they took
the float LiteLLM returns and added floats to floats, so three calls costing
0.0182, 0.0009 and 0.0041 reported 0.023200000000000002.

The provider hands back a float and that is out of our hands. What is in our
hands is that it stops being one before anything adds it up.
"""

from decimal import Decimal

from ensemble.preflight import ModelCheck, PreflightResult
from ensemble.progress import StderrProgress
from ledger import Ledger

# Three real costs from the ledger. Added as floats they drift in the
# fourteenth place, which is enough to print and enough to notice.
DRIFTS = ("0.0182", "0.0009", "0.0041")
EXACT = Decimal("0.0232")


def test_the_float_sum_really_does_drift():
    """The bug this file exists for. If this ever stops failing, delete the rest."""
    assert sum(float(d) for d in DRIFTS) != float(EXACT)


def test_a_decision_total_is_exact(tmp_path):
    path = tmp_path / "calls.jsonl"
    led = Ledger(path)
    for cost in DRIFTS:
        led.record(
            decision_id="d1",
            caller="test",
            model="m",
            role="rater",
            input_tokens=1,
            output_tokens=1,
            cost=float(cost),
        )

    total = led.cost_of("d1")
    assert total == EXACT
    assert str(total) == "0.0232"
    assert isinstance(total, Decimal)


def test_an_absent_ledger_totals_to_an_exact_zero(tmp_path):
    total = Ledger(tmp_path / "nothing.jsonl").cost_of("d1")
    assert total == Decimal("0")
    assert isinstance(total, Decimal)


def test_a_decision_with_no_calls_totals_to_an_exact_zero(tmp_path):
    path = tmp_path / "calls.jsonl"
    led = Ledger(path)
    led.record(
        decision_id="d1",
        caller="test",
        model="m",
        role="rater",
        input_tokens=1,
        output_tokens=1,
        cost=0.01,
    )
    assert led.cost_of("d2") == Decimal("0")


def test_the_running_cost_on_stderr_is_exact(capsys):
    progress = StderrProgress()
    for cost in DRIFTS:
        progress.step("rater", float(cost))

    assert progress.total_cost == EXACT
    assert isinstance(progress.total_cost, Decimal)
    assert "$0.0232 so far" in capsys.readouterr().err


def test_the_preflight_total_is_exact():
    result = PreflightResult(
        checks=tuple(
            ModelCheck(model=f"m{i}", reachable=True, reason=None, cost=float(cost))
            for i, cost in enumerate(DRIFTS)
        )
    )
    assert result.total_cost == EXACT
    assert isinstance(result.total_cost, Decimal)


def test_an_empty_preflight_totals_to_an_exact_zero():
    assert PreflightResult(checks=()).total_cost == Decimal("0")


# The drift does not only come from adding floats up. It arrives already in the
# number: LiteLLM computes price times tokens in binary and handed back
# 2.4750000000000002e-05 for a probe that cost 0.00002475. Summing that exactly
# preserves the noise faithfully, which is not the goal.

NOISY = 2.4750000000000002e-05


def test_a_cost_arriving_with_binary_noise_is_stored_clean(tmp_path):
    path = tmp_path / "calls.jsonl"
    Ledger(path).record(
        decision_id="d1",
        caller="test",
        model="m",
        role="probe",
        input_tokens=1,
        output_tokens=1,
        cost=NOISY,
    )

    assert Ledger(path).cost_of("d1") == Decimal("0.00002475")


def test_the_noise_would_otherwise_survive():
    """Guards the test above. If this fails, the example is no longer noisy."""
    assert str(Decimal(str(NOISY))) != "0.00002475"


def test_a_clean_cost_is_left_alone(tmp_path):
    path = tmp_path / "calls.jsonl"
    Ledger(path).record(
        decision_id="d1",
        caller="test",
        model="m",
        role="rater",
        input_tokens=1,
        output_tokens=1,
        cost=0.0182,
    )
    assert Ledger(path).cost_of("d1") == Decimal("0.0182")


def test_what_is_kept_is_far_below_a_cent(tmp_path):
    """Ten places. A millionth of a cent survives; only binary noise does not."""
    path = tmp_path / "calls.jsonl"
    Ledger(path).record(
        decision_id="d1",
        caller="test",
        model="m",
        role="rater",
        input_tokens=1,
        output_tokens=1,
        cost=0.0000000001,
    )
    assert Ledger(path).cost_of("d1") == Decimal("0.0000000001")
