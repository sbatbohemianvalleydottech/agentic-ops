"""Whether anything actually closed.

An RCA with six action items where five are open at ninety days says something
about the organisation rather than the incident, and no single review surfaces it.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from rca_agent.completion import report_completion
from rca_agent.rubric import load_rubric
from rca_agent.types import RCA, ActionItem, Category

AS_OF = datetime(2026, 9, 1)


@pytest.fixture
def rubric():
    return load_rubric()


def item(title, state="closed", created=datetime(2026, 6, 1), evidence="PR 1"):
    return ActionItem(
        title=title,
        state=state,
        created=created,
        owner="Rae Lindqvist",
        due=datetime(2026, 7, 1),
        tracker_ref="X-1",
        category=Category.PREVENT,
        closure_evidence=evidence if state == "closed" else None,
    )


def rca(rca_id, items, closed_at=datetime(2026, 6, 2), exported=datetime(2026, 6, 3)):
    return RCA(
        rca_id=rca_id, severity="sev2", timeline=(), impact="1 thing",
        stated_cause="a cause", contributing_factors=("a", "b"), narrative="n",
        participants=(), action_items=tuple(items),
        closed_at=closed_at, followups_exported_at=exported,
    )


def test_closure_rate_and_median_open_age_match_a_hand_computation(rubric):
    corpus = [
        rca("rca-1", [
            item("a"),
            item("b"),
            item("c", state="open", created=datetime(2026, 8, 22)),  # 10 days
            item("d", state="open", created=datetime(2026, 8, 2)),   # 30 days
        ])
    ]

    report = report_completion(corpus, rubric, AS_OF)

    assert report.total_items == 4
    assert report.closed_items == 2
    assert report.closure_rate == Decimal("0.50")
    assert report.median_open_age_days == 20  # median of 10 and 30


def test_no_open_items_reports_no_median_rather_than_zero(rubric):
    report = report_completion([rca("rca-1", [item("a")])], rubric, AS_OF)

    assert report.median_open_age_days is None


def test_closed_with_and_without_evidence_are_counted_separately(rubric):
    """Different claims about the same word."""
    corpus = [rca("rca-1", [item("a"), item("b", evidence=None), item("c", evidence=None)])]

    report = report_completion(corpus, rubric, AS_OF)

    assert report.closed_items == 3
    assert report.closed_without_evidence == 2


def test_an_rca_past_the_export_window_with_no_tracker_export_is_a_breach(rubric):
    corpus = [rca("rca-late", [item("a")], closed_at=datetime(2026, 6, 1), exported=None)]

    report = report_completion(corpus, rubric, AS_OF)

    assert "rca-late" in report.export_policy_breaches


def test_an_export_inside_the_window_is_not_a_breach(rubric):
    corpus = [
        rca("rca-ok", [item("a")], closed_at=datetime(2026, 6, 1),
            exported=datetime(2026, 6, 5))
    ]

    report = report_completion(corpus, rubric, AS_OF)

    assert report.export_policy_breaches == ()


def test_a_still_open_rca_is_not_yet_subject_to_the_export_window(rubric):
    """Follow-ups cannot be overdue for an incident nobody has closed."""
    corpus = [rca("rca-open", [item("a")], closed_at=None, exported=None)]

    report = report_completion(corpus, rubric, AS_OF)

    assert report.export_policy_breaches == ()


def test_an_action_item_repeated_across_rcas_is_reported(rubric):
    """A recurring action item is evidence the first one never landed."""
    corpus = [
        rca("rca-1", [item("Set a lock timeout on migrations")]),
        rca("rca-2", [item("Set a lock timeout on migrations"), item("Something else")]),
    ]

    report = report_completion(corpus, rubric, AS_OF)

    assert "Set a lock timeout on migrations" in report.repeated_action_items
    assert "Something else" not in report.repeated_action_items


def test_an_empty_corpus_reports_zero_rather_than_dividing_by_zero(rubric):
    report = report_completion([], rubric, AS_OF)

    assert report.total_items == 0
    assert report.closure_rate == Decimal("0")
