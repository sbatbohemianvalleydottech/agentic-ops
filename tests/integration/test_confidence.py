"""Confidence is a judgement, so Principle I applies to it.

A savings estimate without a confidence level is a guess presented as a finding.
A confidence level that averages two disagreeing assessments is worse: it is a
fabricated agreement wearing a number.
"""

from datetime import datetime
from decimal import Decimal

from cost_agent.classify import Finding, RootCause, Rule
from cost_agent.confidence import rate_confidence
from cost_agent.drivers import Driver
from ensemble.orchestrator import Rater
from ensemble.providers.fake import FakeProvider
from ledger import Ledger

AS_OF = datetime(2026, 9, 1)


def driver() -> Driver:
    return Driver(
        root_cause=RootCause.CAPACITY_MANAGEMENT,
        absent_practice="capacity is provisioned once and never revisited",
        cloud="gcp",
        findings=(
            Finding("r-1", Rule.UNDER_UTILISED, {"utilisation_avg": 0.30},
                    Decimal("0.30")),
            Finding("r-2", Rule.OVERSIZED, {"provisioned_to_peak": 2.4},
                    Decimal("0.25")),
        ),
        annual_cost=Decimal("120000.00"),
        share_of_bill=Decimal("0.34"),
        single_resource=False,
        savings_low=Decimal("18000.00"),
        savings_high=Decimal("36000.00"),
    )


def test_agreeing_assessors_and_a_satisfied_judge_set_the_confidence(tmp_path):
    provider = FakeProvider(grades={"model-a": "high", "model-b": "high"})

    rated = rate_confidence(
        driver(),
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=Ledger(tmp_path / "calls.jsonl"),
        as_of=AS_OF,
    )

    assert rated.confidence == "high"


def test_disagreeing_assessors_produce_needs_review_not_a_middle_value(tmp_path):
    """The averaged answer here would be 'medium', which no assessor said and no
    evidence supports."""
    provider = FakeProvider(grades={"model-a": "high", "model-b": "low"})

    rated = rate_confidence(
        driver(),
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=Ledger(tmp_path / "calls.jsonl"),
        as_of=AS_OF,
    )

    assert rated.confidence == "NEEDS_REVIEW"
    assert "medium" not in rated.confidence


def test_a_judge_rejecting_a_unanimous_rating_also_needs_review(tmp_path):
    provider = FakeProvider(
        grades={"model-a": "high", "model-b": "high"}, justified=False
    )

    rated = rate_confidence(
        driver(),
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=Ledger(tmp_path / "calls.jsonl"),
        as_of=AS_OF,
    )

    assert rated.confidence == "NEEDS_REVIEW"


def test_every_model_call_is_recorded_against_the_driver(tmp_path):
    provider = FakeProvider(grades={"model-a": "high", "model-b": "high"})
    ledger = Ledger(tmp_path / "calls.jsonl")

    rate_confidence(
        driver(),
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=ledger,
        as_of=AS_OF,
    )

    lines = (tmp_path / "calls.jsonl").read_text().strip().splitlines()
    assert len(lines) == 3  # two assessors plus one judge


def test_the_evidence_given_to_assessors_cites_every_finding(tmp_path):
    """Principle II. An assessor rating a driver it cannot see the basis for is
    rating a headline."""
    provider = FakeProvider(grades={"model-a": "high", "model-b": "high"})

    rate_confidence(
        driver(),
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "judge-model"),
        ledger=Ledger(tmp_path / "calls.jsonl"),
        as_of=AS_OF,
    )

    assert provider.judge_calls[0]["subject"]
