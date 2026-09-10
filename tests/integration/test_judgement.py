"""Judgement dimensions, each independently gated.

One overall grade would tell a reviewer nothing about what to look at, and one
contested dimension would halt the whole review. Per-dimension means the output
is "cause-versus-trigger is contested, the rest agreed", which is actionable.
"""

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from ensemble.providers import Call, Usage
from ensemble.types import JudgeVerdict, RaterVerdict
from rca_agent.judgement import assess_judgement
from rca_agent.rubric import load_rubric
from rca_agent.types import RCA, ActionItem, Category, Dimension, TimelineMoment

AS_OF = datetime(2026, 9, 1)


@dataclass
class ByDimensionProvider:
    """Scripted per (dimension, model), so one dimension can be contested while
    the others agree. The shared FakeProvider grades per model only."""

    grades: dict[tuple[str, str], str]
    justified: dict[str, bool] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def grade(self, rubric, evidence, model):
        self.calls.append((rubric.name, model))
        return Call(
            verdict=RaterVerdict(
                rater=model, grade=self.grades[(rubric.name, model)], reasoning="because"
            ),
            usage=Usage(input_tokens=800, output_tokens=200, cost=0.004),
        )

    def judge(self, rubric, evidence, grade, model):
        return Call(
            verdict=JudgeVerdict(
                justified=self.justified.get(rubric.name, True), reasoning="judged"
            ),
            usage=Usage(input_tokens=600, output_tokens=150, cost=0.002),
        )


@pytest.fixture
def rubric():
    return load_rubric()


@pytest.fixture
def rca():
    return RCA(
        rca_id="rca-hollow",
        severity="sev1",
        timeline=(TimelineMoment("detection", datetime(2026, 4, 14, 14, 2)),),
        impact="2,310 users saw elevated latency for 80 minutes.",
        stated_cause="A bad deploy went out and caused elevated latency.",
        contributing_factors=("The deploy changed the connection pool.",),
        narrative="The on-call reverted the deploy at 14:41.",
        participants=("Ines Duarte",),
        action_items=(
            ActionItem(
                title="Review connection pool settings before deploys",
                state="open",
                created=datetime(2026, 4, 16),
                owner="Ines Duarte",
                due=datetime(2026, 5, 1),
                tracker_ref="API-901",
                category=Category.PREVENT,
            ),
        ),
    )


def agreeing(rubric, grade="adequate"):
    return {
        (dimension.value, model): grade
        for dimension in (
            Dimension.CAUSE_NOT_TRIGGER,
            Dimension.NO_ALTERNATE_REALITY,
            Dimension.ACTIONS_WOULD_PREVENT,
        )
        for model in ("model-a", "model-b")
    }


def raters_for(provider):
    from ensemble.orchestrator import Rater

    return (
        [Rater(provider, "model-a"), Rater(provider, "model-b")],
        Rater(provider, "judge-model"),
    )


def test_every_judgement_dimension_is_assessed(rca, rubric, ledger):
    provider = ByDimensionProvider(grades=agreeing(rubric))
    raters, judge = raters_for(provider)

    grades = assess_judgement(rca, rubric, raters=raters, judge=judge, ledger=ledger)

    assert {g.dimension for g in grades} == {
        Dimension.CAUSE_NOT_TRIGGER,
        Dimension.NO_ALTERNATE_REALITY,
        Dimension.ACTIONS_WOULD_PREVENT,
    }


def test_a_contested_dimension_does_not_suppress_the_others(rca, rubric, ledger):
    """The whole reason for gating per dimension rather than once."""
    grades = agreeing(rubric)
    grades[(Dimension.CAUSE_NOT_TRIGGER.value, "model-b")] = "strong"
    provider = ByDimensionProvider(grades=grades)
    raters, judge = raters_for(provider)

    results = {
        g.dimension: g
        for g in assess_judgement(rca, rubric, raters=raters, judge=judge, ledger=ledger)
    }

    assert results[Dimension.CAUSE_NOT_TRIGGER].needs_human_review is True
    assert results[Dimension.NO_ALTERNATE_REALITY].needs_human_review is False
    assert results[Dimension.NO_ALTERNATE_REALITY].grade == "adequate"


def test_a_contested_dimension_has_no_grade_and_is_not_averaged(rca, rubric, ledger):
    grades = agreeing(rubric)
    grades[(Dimension.CAUSE_NOT_TRIGGER.value, "model-a")] = "weak"
    grades[(Dimension.CAUSE_NOT_TRIGGER.value, "model-b")] = "strong"
    provider = ByDimensionProvider(grades=grades)
    raters, judge = raters_for(provider)

    result = next(
        g
        for g in assess_judgement(rca, rubric, raters=raters, judge=judge, ledger=ledger)
        if g.dimension is Dimension.CAUSE_NOT_TRIGGER
    )

    assert result.needs_human_review is True
    assert result.grade is None  # "adequate" would be a fabricated middle


def test_a_judge_rejecting_a_unanimous_grade_also_needs_review(rca, rubric, ledger):
    provider = ByDimensionProvider(
        grades=agreeing(rubric),
        justified={Dimension.ACTIONS_WOULD_PREVENT.value: False},
    )
    raters, judge = raters_for(provider)

    result = next(
        g
        for g in assess_judgement(rca, rubric, raters=raters, judge=judge, ledger=ledger)
        if g.dimension is Dimension.ACTIONS_WOULD_PREVENT
    )

    assert result.needs_human_review is True


def test_a_dimension_halted_by_failure_says_so_rather_than_blaming_disagreement(
    rca, rubric, ledger
):
    """The exact wrong message the first live run produced. Nobody disagreed;
    every call errored."""

    @dataclass
    class FailingProvider:
        def grade(self, rubric, evidence, model):
            return Call(
                verdict=None,
                usage=Usage(),
                error="BadRequestError: credit balance is too low",
            )

        def judge(self, rubric, evidence, grade, model):
            return Call(verdict=None, usage=Usage(), error="not reached")

    raters, judge = raters_for(FailingProvider())

    grades = assess_judgement(rca, rubric, raters=raters, judge=judge, ledger=ledger)

    reasoning = grades[0].reasoning
    assert "credit balance is too low" in reasoning
    assert "did not agree" not in reasoning


def test_one_ledger_record_per_call_across_every_dimension(
    rca, rubric, ledger, ledger_path
):
    provider = ByDimensionProvider(grades=agreeing(rubric))
    raters, judge = raters_for(provider)

    assess_judgement(rca, rubric, raters=raters, judge=judge, ledger=ledger)

    lines = ledger_path.read_text().strip().splitlines()
    assert len(lines) == 9  # three dimensions x (two raters + one judge)
