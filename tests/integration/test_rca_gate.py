"""rca_agent as a pipeline gate.

It used to find five defective reviews and exit 0, which meant it could report
a problem and pass the build in the same breath. Structural defects are
objective and free to check, so an incident review missing a detection
timestamp is exactly the kind of thing that should not merge.

Gating is opt-in. Reporting stays the default, because a tool that starts
failing builds the day someone upgrades it is a tool people pin and forget.
"""

import shutil
from pathlib import Path

import pytest

from ci import Exit
from rca_agent.cli import main

CORPUS = Path(__file__).resolve().parents[2] / "rca_agent" / "fixtures" / "corpus"
CLEAN = ("rca-good.json", "rca-abandoned.json", "rca-hollow.json")


@pytest.fixture
def clean_corpus(tmp_path):
    """The three fixtures that break no structural check."""
    for name in CLEAN:
        shutil.copy(CORPUS / name, tmp_path / name)
    return tmp_path


def run(capsys, *args):
    code = main([str(a) for a in args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_reporting_is_the_default_and_never_fails_a_build(capsys):
    code, out, _ = run(capsys, "--corpus", CORPUS, "--as-of", "2026-09-01")
    assert code == Exit.OK
    assert "rca-blame" in out


def test_the_gate_blocks_on_a_corpus_with_defects(capsys):
    code, out, err = run(
        capsys, "--corpus", CORPUS, "--as-of", "2026-09-01", "--fail-on-defects"
    )
    assert code == Exit.BLOCKED
    # The report still prints. A gate that blocks without saying why is useless.
    assert "rca-blame" in out
    assert "5" in err


def test_the_gate_passes_a_clean_corpus(capsys, clean_corpus):
    code, _, err = run(
        capsys, "--corpus", clean_corpus, "--as-of", "2026-09-01", "--fail-on-defects"
    )
    assert code == Exit.OK
    assert err == "" or "0 of 3" in err


def test_the_gate_names_which_reviews_failed(capsys):
    _, _, err = run(
        capsys, "--corpus", CORPUS, "--as-of", "2026-09-01", "--fail-on-defects"
    )
    for defective in ("rca-blame", "rca-broken-timeline", "rca-no-tickets"):
        assert defective in err


def test_a_clean_review_is_not_named(capsys):
    _, _, err = run(
        capsys, "--corpus", CORPUS, "--as-of", "2026-09-01", "--fail-on-defects"
    )
    assert "rca-hollow" not in err, (
        "rca-hollow passes every structural check; naming it would tell a "
        "pipeline the free layer caught something it did not"
    )


def test_the_verdict_goes_to_stderr_so_stdout_stays_the_report(capsys):
    _, out, err = run(
        capsys, "--corpus", CORPUS, "--as-of", "2026-09-01", "--fail-on-defects"
    )
    assert "blocked" in err.lower()
    assert "blocked" not in out.lower()
