from datetime import datetime

import pytest

from ensemble.types import EvidenceRecord, Rubric


def test_rubric_rejects_a_scale_with_fewer_than_two_grades():
    """A one-grade scale makes disagreement impossible and the gate meaningless."""
    with pytest.raises(ValueError):
        Rubric(name="performance", criteria="assess the year", scale=("meeting",))


def test_evidence_record_rejects_an_empty_reference():
    """Principle II: a claim resting on an unreferenceable record has to be dropped,
    so the record itself is useless."""
    with pytest.raises(ValueError):
        EvidenceRecord(
            source="jira",
            timestamp=datetime(2026, 3, 1),
            ref="",
            content="closed PLATFORM-412",
        )
