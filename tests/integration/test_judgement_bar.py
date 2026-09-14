"""The paid pass does not run on a document that is not a review.

Driven from argv against a counting provider, so what is asserted is the number
of calls a real run would have made. No network: the provider and the probe are
both replaced, the same way the other paid-path tests do it, so this runs in the
CI job that installs no provider library at all.

The number is the whole point. A test that only checked the report said the
right thing would pass against an implementation that printed the explanation
and paid anyway.
"""

import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from ci import Exit
from ensemble.preflight import ModelCheck
from ensemble.providers.fake import FakeProvider
from rca_agent.cli import main as rca_main

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "rca_agent" / "fixtures" / "corpus"
NOT_A_REVIEW = REPO / "rca_agent" / "fixtures" / "not-a-review" / "status-page-entry.json"

AGREE = {"anthropic/claude-opus-5": "adequate", "gemini/gemini-3.8-flash": "adequate"}


class Counting(FakeProvider):
    """Every rater call, counted. The judge already records its own."""

    def __init__(self):
        super().__init__(grades=AGREE)
        self.rater_calls = []

    def grade(self, rubric, evidence, model):
        self.rater_calls.append((evidence.subject, rubric.name, model))
        return super().grade(rubric, evidence, model)


@pytest.fixture
def provider(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    monkeypatch.chdir(tmp_path)

    import ensemble.preflight as preflight_module

    monkeypatch.setattr(
        preflight_module,
        "_live_probe",
        lambda model: ModelCheck(model=model, reachable=True, reason=None, cost=0.0),
    )

    counting = Counting()
    stub = types.ModuleType("ensemble.providers.litellm")
    stub.LiteLLMProvider = lambda: counting
    monkeypatch.setitem(sys.modules, "ensemble.providers.litellm", stub)
    return counting


@pytest.fixture
def mixed(tmp_path):
    """One document that is a review and one that is not."""
    corpus = tmp_path / "mixed"
    corpus.mkdir()
    shutil.copy(CORPUS / "rca-good.json", corpus)
    shutil.copy(NOT_A_REVIEW, corpus)
    return corpus


def subjects(provider):
    return {subject for subject, _, _ in provider.rater_calls}


def test_only_the_real_review_is_paid_for(capsys, provider, mixed):
    rca_main(["--corpus", str(mixed), "--judgement"])
    assert subjects(provider) == {"incident review rca-good"}


def test_the_other_one_still_appears_in_the_report(capsys, provider, mixed):
    """Skipped is not omitted. A reader has to see it was looked at."""
    rca_main(["--corpus", str(mixed), "--judgement"])
    out = capsys.readouterr().out
    assert "RCA status-page-entry" in out


def test_the_report_says_why_it_was_not_judged(capsys, provider, mixed):
    rca_main(["--corpus", str(mixed), "--judgement"])
    out = capsys.readouterr().out
    assert "not judged" in out
    assert "contributing factors" in out
    assert "action items" in out


def test_judge_anyway_pays_for_both(capsys, provider, mixed):
    rca_main(["--corpus", str(mixed), "--judgement", "--judge-anyway"])
    assert subjects(provider) == {
        "incident review rca-good",
        "incident review status-page-entry",
    }


def test_a_corpus_of_nothing_but_non_reviews_calls_nobody(capsys, provider, tmp_path):
    corpus = tmp_path / "none"
    corpus.mkdir()
    shutil.copy(NOT_A_REVIEW, corpus)
    rca_main(["--corpus", str(corpus), "--judgement"])
    assert provider.rater_calls == []
    assert provider.judge_calls == []


def test_the_shipped_corpus_is_judged_exactly_as_before(capsys, provider):
    """Every fixture in it clears the bar, so this feature must not touch it."""
    rca_main(["--corpus", str(CORPUS), "--judgement"])
    assert len(subjects(provider)) == len(list(CORPUS.glob("*.json")))


def test_the_exit_code_does_not_move(capsys, provider, mixed):
    """Refusing to pay is not a finding."""
    assert rca_main(["--corpus", str(mixed), "--judgement"]) == Exit.OK
    assert rca_main(["--corpus", str(mixed), "--judgement", "--judge-anyway"]) == Exit.OK


def test_the_bar_does_not_reach_the_defect_gate(capsys, provider, tmp_path):
    """--fail-on-defects gates on structural defects. Not being a review is not
    one of those, and this document has real defects of its own, so the check is
    that the code comes from those and not from the bar."""
    corpus = tmp_path / "one"
    corpus.mkdir()
    shutil.copy(NOT_A_REVIEW, corpus)
    code = rca_main(["--corpus", str(corpus), "--judgement", "--fail-on-defects"])
    err = capsys.readouterr().err
    assert code == Exit.BLOCKED
    assert "not a review" not in err


def test_nothing_is_written_to_the_ledger_for_a_skipped_review(
    capsys, provider, tmp_path
):
    """A ledger row for a call nobody made would be a lie about spend."""
    corpus = tmp_path / "none"
    corpus.mkdir()
    shutil.copy(NOT_A_REVIEW, corpus)
    rca_main(["--corpus", str(corpus), "--judgement"])

    rows = [
        json.loads(line)
        for line in (tmp_path / ".ledger" / "calls.jsonl").read_text().splitlines()
    ]
    # The preflight probe still runs and still meters itself. Nothing else does.
    assert {row["decision_id"] for row in rows} == {"preflight"}
