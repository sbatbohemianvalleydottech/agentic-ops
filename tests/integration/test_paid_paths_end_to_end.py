"""The paid paths, driven from argv, against the fake provider.

Coverage said cost_agent/cli.py was 49% and rca_agent/cli.py 56%, and the
uncovered lines were the credential check, the preflight call, the provider
construction and the wiring into the paid layer. The judgement logic underneath
was well tested; nothing tested the code that reaches it.

That is the worst place to have the gap. Every failure of the first live run
lived there: a retired model, a workspace-scoped key, an unfunded account, and
an empty value in .env that a library loaded behind us. None of those are
failures of the gate. They are failures of the wiring.

No network here. The provider and the probe are both replaced, so this runs in
CI for nothing and proves the path exists, not that a vendor answers.
"""

import sys
import types
from pathlib import Path

import pytest

from ci import Exit
from cost_agent.cli import main as cost_main
from ensemble.preflight import ModelCheck, PreflightResult
from ensemble.providers.fake import FakeProvider
from rca_agent.cli import main as rca_main

FIXTURES = Path(__file__).resolve().parents[2]
COSTS = FIXTURES / "cost_agent" / "fixtures" / "estate_a" / "costs.csv"
INVENTORY = FIXTURES / "cost_agent" / "fixtures" / "estate_a" / "inventory.json"
CORPUS = FIXTURES / "rca_agent" / "fixtures" / "corpus"

SPLIT = {"anthropic/claude-opus-5": "low", "gemini/gemini-3.8-flash": "high"}


@pytest.fixture
def credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    monkeypatch.chdir(tmp_path)  # the ledger is written relative to cwd
    return tmp_path


def _stub_adapter(monkeypatch, provider_factory):
    """Stand in for the vendor adapter without importing it.

    A module object in sys.modules rather than a patched attribute, so this
    works with the provider library absent. That matters: the wiring being
    tested is what a paid run goes through, and the core CI job installs no
    provider library at all. Patching the real adapter would have made these
    tests skip in exactly the job that most needs them to run.
    """
    stub = types.ModuleType("ensemble.providers.litellm")
    stub.LiteLLMProvider = provider_factory
    monkeypatch.setitem(sys.modules, "ensemble.providers.litellm", stub)


@pytest.fixture
def no_vendor(monkeypatch):
    """Replace the provider and the probe. Nothing opens a socket."""
    import ensemble.preflight as preflight_module

    def ok(model):
        return ModelCheck(model=model, reachable=True, reason=None, cost=0.0)

    monkeypatch.setattr(preflight_module, "_live_probe", ok)
    _stub_adapter(monkeypatch, lambda: FakeProvider(grades=SPLIT))


def one_review(tmp_path):
    import shutil

    target = tmp_path / "one"
    target.mkdir()
    shutil.copy(CORPUS / "rca-hollow.json", target)
    return target


def test_cost_agent_runs_the_confidence_pass_from_argv(capsys, credentials, no_vendor):
    code = cost_main([
        "--costs", str(COSTS), "--inventory", str(INVENTORY),
        "--as-of", "2026-09-01", "--confidence",
    ])
    out = capsys.readouterr().out

    assert code == Exit.OK
    assert "Confidence:" in out
    # The two fake raters disagree, so every driver must land on NEEDS_REVIEW
    # rather than on a middle value.
    assert "NEEDS_REVIEW" in out


def test_cost_agent_meters_the_confidence_pass_it_just_ran(credentials, no_vendor):
    cost_main([
        "--costs", str(COSTS), "--inventory", str(INVENTORY),
        "--as-of", "2026-09-01", "--confidence",
    ])
    assert (credentials / ".ledger" / "calls.jsonl").exists()


def test_cost_agent_refuses_the_paid_pass_with_no_credentials(capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    code = cost_main([
        "--costs", str(COSTS), "--inventory", str(INVENTORY),
        "--as-of", "2026-09-01", "--confidence",
    ])
    err = capsys.readouterr().err

    assert code == Exit.UNJUDGED
    assert "ANTHROPIC_API_KEY" in err


def test_rca_agent_runs_the_judgement_pass_from_argv(capsys, credentials, no_vendor):
    code = rca_main([
        "--corpus", str(one_review(credentials)),
        "--as-of", "2026-09-01", "--judgement",
    ])
    out = capsys.readouterr().out

    assert code == Exit.OK
    assert "Judgement dimensions" in out
    assert "CONTESTED" in out


def test_rca_agent_refuses_the_judgement_pass_with_no_credentials(
    capsys, monkeypatch, tmp_path
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    code = rca_main([
        "--corpus", str(CORPUS), "--as-of", "2026-09-01", "--judgement",
    ])
    err = capsys.readouterr().err

    assert code == Exit.UNJUDGED
    assert "GEMINI_API_KEY" in err


def test_the_check_flag_probes_and_reports(capsys, credentials, no_vendor):
    code = rca_main(["--corpus", str(CORPUS), "--check"])
    out = capsys.readouterr().out

    assert code == Exit.OK
    assert "Preflight" in out
    assert "ok" in out


def test_the_check_flag_fails_when_a_model_is_unreachable(
    capsys, credentials, monkeypatch
):
    """A dead model must not report ok, and must not exit 0."""
    import ensemble.preflight as preflight_module

    monkeypatch.setattr(
        preflight_module,
        "_live_probe",
        lambda model: ModelCheck(
            model=model, reachable=False, reason="401 unauthorised", cost=0.0
        ),
    )

    code = rca_main(["--corpus", str(CORPUS), "--check"])
    out = capsys.readouterr().out

    assert code == Exit.UNJUDGED
    assert "FAIL" in out


def test_a_failed_preflight_aborts_before_the_paid_pass(capsys, credentials, monkeypatch):
    """The probe exists to stop the expensive run. It has to actually stop it."""
    import ensemble.preflight as preflight_module

    called = []

    class Exploding(FakeProvider):
        def grade(self, *a, **k):
            called.append(1)
            raise AssertionError("the paid pass ran after a failed preflight")

    monkeypatch.setattr(
        preflight_module,
        "_live_probe",
        lambda model: ModelCheck(
            model=model, reachable=False, reason="no credit", cost=0.0
        ),
    )
    _stub_adapter(monkeypatch, lambda: Exploding(grades=SPLIT))

    code = cost_main([
        "--costs", str(COSTS), "--inventory", str(INVENTORY),
        "--as-of", "2026-09-01", "--confidence",
    ])

    assert code == Exit.UNJUDGED
    assert called == []
    assert "Aborting before the run" in capsys.readouterr().err


def test_preflight_result_is_reachable_as_a_whole():
    """Guards the fixture above: an all-ok preflight has to read as ok."""
    assert PreflightResult(
        checks=(ModelCheck(model="m", reachable=True, reason=None, cost=0.0),)
    ).ok
