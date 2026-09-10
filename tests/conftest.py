"""Shared test fixtures.

The rubric and the resource factory were each defined identically in several
files. Duplicated setup drifts: one copy gains a field, the others quietly go on
testing a shape that no longer exists.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from cost_agent.inputs import Resource
from cost_agent.thresholds import load_thresholds
from ensemble.types import (
    EvidenceBundle,
    EvidenceRecord,
    JudgeVerdict,
    RaterVerdict,
    Rubric,
)
from ledger import Ledger


@pytest.fixture
def bands() -> Rubric:
    """The three-point scale most agents in this repo grade against."""
    return Rubric(
        name="performance",
        criteria="assess the year against the rubric",
        scale=("not meeting", "meeting", "exceeding"),
    )


@pytest.fixture
def satisfied_judge() -> JudgeVerdict:
    return JudgeVerdict(justified=True, reasoning="evidence supports the band")


@pytest.fixture
def make_rater():
    def _make(name: str, grade: str, reasoning: str = "because") -> RaterVerdict:
        return RaterVerdict(rater=name, grade=grade, reasoning=reasoning)

    return _make


@pytest.fixture
def evidence() -> EvidenceBundle:
    return EvidenceBundle(
        subject="engineer-07",
        records=(
            EvidenceRecord(
                source="jira",
                timestamp=datetime(2026, 3, 1),
                ref="PLATFORM-412",
                content="closed the multi-region rollout",
            ),
        ),
    )


@pytest.fixture
def ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "calls.jsonl")


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "calls.jsonl"


@pytest.fixture
def thresholds():
    return load_thresholds()


@pytest.fixture
def as_of() -> datetime:
    """Analysis date. A parameter rather than the clock, so runs reproduce."""
    return datetime(2026, 9, 1)


@pytest.fixture
def make_resource():
    """A healthy compute resource by default. Override only what the test is about."""

    def _make(resource_id: str = "r-1", cost: str = "1000.00", **overrides) -> Resource:
        base = dict(
            resource_id=resource_id,
            cloud="gcp",
            service="anything",
            period_cost=Decimal(cost),
            kind="compute",
            tags={"owner": "platform"},
            utilisation_avg=0.75,
            age_days=100,
            attached=True,
            commitment_covered=True,
        )
        return Resource(**{**base, **overrides})

    return _make
