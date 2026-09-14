"""Input that cannot be read is exit 2, in all three, with a message.

Found by writing the CI job rather than by reading the code. Pointed at a file
that does not exist, cost_agent printed a FileNotFoundError traceback and
exited 1, which in the shared contract means "ran, judged, and the answer is
stop". A pipeline would have read a typo as a finding.

rca_agent was worse: an empty or missing corpus directory exited 0. A typo in a
path produced a green build and an empty report, which is the exact shape of
the failure this repository exists to object to: a confident answer returned
successfully with nothing behind it.
"""

import pytest

from ci import Exit
from cost_agent.cli import main as cost_main
from plan_cost.cli import main as plan_main
from rca_agent.cli import main as rca_main

COSTS = "cost_agent/fixtures/estate_a/costs.csv"
INVENTORY = "cost_agent/fixtures/estate_a/inventory.json"


def run(capsys, entry, *args):
    code = entry([str(a) for a in args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cost_agent_refuses_a_missing_inventory(capsys):
    code, out, err = run(
        capsys, cost_main, "--costs", COSTS, "--inventory", "nope.json",
        "--as-of", "2026-09-01",
    )
    assert code == Exit.UNJUDGED
    assert "nope.json" in err
    assert "Traceback" not in err and "Traceback" not in out


def test_cost_agent_refuses_a_missing_costs_file(capsys):
    code, _, err = run(
        capsys, cost_main, "--costs", "nope.csv", "--inventory", INVENTORY,
        "--as-of", "2026-09-01",
    )
    assert code == Exit.UNJUDGED
    assert "nope.csv" in err


def test_rca_agent_refuses_a_corpus_directory_that_is_not_there(capsys):
    code, _, err = run(capsys, rca_main, "--corpus", "nope", "--as-of", "2026-09-01")
    assert code == Exit.UNJUDGED
    assert "nope" in err


def test_rca_agent_refuses_an_empty_corpus(capsys, tmp_path):
    """Zero reviews is not a clean corpus. It is nothing to judge."""
    code, _, err = run(capsys, rca_main, "--corpus", tmp_path, "--as-of", "2026-09-01")
    assert code == Exit.UNJUDGED
    assert "no" in err.lower()


def test_plan_cost_already_refused_and_still_does(capsys):
    code, _, err = run(capsys, plan_main, "--plan", "nope.json", "--env", "staging")
    assert code == Exit.UNJUDGED
    assert "nope.json" in err


@pytest.mark.parametrize(
    "entry,args",
    [
        (cost_main, ["--costs", "nope.csv", "--inventory", INVENTORY, "--as-of", "2026-09-01"]),
        (rca_main, ["--corpus", "nope", "--as-of", "2026-09-01"]),
        (plan_main, ["--plan", "nope.json", "--env", "staging"]),
    ],
)
def test_a_refusal_never_prints_a_report(capsys, entry, args):
    """2 must not be mistakable for a verdict, in any of the three."""
    _, out, _ = run(capsys, entry, *args)
    assert out == ""
