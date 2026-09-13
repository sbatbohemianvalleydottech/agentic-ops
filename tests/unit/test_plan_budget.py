"""The threshold, taken from the organisation's own budget.

There is no per-change threshold in the budget API, so the tool derives one and
shows the arithmetic. What it cannot do is know current spend, which is stated
in the report rather than papered over: this judges one change in isolation.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from plan_cost.budget import BudgetError, threshold_from

BUDGETS = Path(__file__).resolve().parents[2] / "plan_cost" / "fixtures" / "budget" / "budgets.json"


def budgets():
    return json.loads(BUDGETS.read_text(encoding="utf-8"))


def test_the_threshold_is_the_amount_times_the_lowest_threshold_rule():
    threshold = threshold_from(budgets(), name="platform-monthly")
    assert threshold.monthly == Decimal("200.00")


def test_the_arithmetic_is_shown_so_a_reader_can_disagree_with_it():
    threshold = threshold_from(budgets(), name="platform-monthly")
    assert "800" in threshold.derivation
    assert "25" in threshold.derivation


def test_the_budget_filter_is_carried_so_coverage_is_visible():
    threshold = threshold_from(budgets(), name="platform-monthly")
    assert "projects/123456789012" in threshold.applies_to


def test_more_than_one_budget_without_a_name_is_an_error_listing_them():
    with pytest.raises(BudgetError) as raised:
        threshold_from(budgets(), name=None)
    message = str(raised.value)
    assert "platform-monthly" in message and "data-platform-last-period" in message


def test_a_single_budget_needs_no_name():
    one = {"budgets": [budgets()["budgets"][0]]}
    assert threshold_from(one, name=None).monthly == Decimal("200.00")


def test_a_budget_with_no_absolute_amount_is_refused_with_its_reason():
    """A budget set to last period's spend carries no figure in the response, so
    there is nothing to derive a threshold from."""
    with pytest.raises(BudgetError) as raised:
        threshold_from(budgets(), name="data-platform-last-period")
    assert "lastPeriodAmount" in str(raised.value)


def test_a_name_nobody_has_is_an_error():
    with pytest.raises(BudgetError):
        threshold_from(budgets(), name="does-not-exist")


def test_units_and_nanos_make_one_amount():
    document = {
        "budgets": [
            {
                "displayName": "fractional",
                "budgetFilter": {"projects": ["projects/1"]},
                "amount": {"specifiedAmount": {"currencyCode": "USD", "units": "800",
                                               "nanos": 500000000}},
                "thresholdRules": [{"thresholdPercent": 0.5}],
            }
        ]
    }
    assert threshold_from(document, name=None).monthly == Decimal("400.25")


def test_a_budget_with_no_threshold_rules_cannot_set_a_line():
    document = {
        "budgets": [
            {
                "displayName": "no-rules",
                "budgetFilter": {},
                "amount": {"specifiedAmount": {"currencyCode": "USD", "units": "800",
                                               "nanos": 0}},
                "thresholdRules": [],
            }
        ]
    }
    with pytest.raises(BudgetError) as raised:
        threshold_from(document, name=None)
    assert "threshold" in str(raised.value)
