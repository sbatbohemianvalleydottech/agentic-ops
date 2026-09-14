"""An ambiguous budget must not quietly become a looser threshold.

A cold reader found this: the README promised that two budgets and no name is
an error, and the tool warned on stderr and carried on against the policy
file's threshold instead. In the shipped fixtures that meant judging a plan
against $250.00 when the operator had asked for the budget's $200.00, so the
gate got looser exactly when nobody was looking. That is the failure this tool
says is impossible for a missing environment, happening for a budget.

The distinction now drawn: naming a budget that is not there, or naming none
when there are several, is the operator's input being wrong and is fatal. A
budget that is correctly identified but cannot yield a threshold is a fact
about the data, and still warns and falls back.
"""

import pytest

from plan_cost.budget import BudgetError, BudgetSelectionError, threshold_from

TWO = {
    "budgets": [
        {
            "displayName": "platform-monthly",
            "amount": {"specifiedAmount": {"units": "800"}},
            "thresholdRules": [{"thresholdPercent": 0.25}],
        },
        {
            "displayName": "data-platform-last-period",
            "amount": {"lastPeriodAmount": {}},
            "thresholdRules": [{"thresholdPercent": 0.5}],
        },
    ]
}


def test_several_budgets_and_no_name_is_fatal():
    with pytest.raises(BudgetSelectionError) as raised:
        threshold_from(TWO, name=None)

    message = str(raised.value)
    assert "2 budgets" in message
    assert "platform-monthly" in message
    assert "--budget-name" in message


def test_naming_a_budget_that_is_not_there_is_fatal():
    with pytest.raises(BudgetSelectionError) as raised:
        threshold_from(TWO, name="no-such-budget")

    assert "no-such-budget" in str(raised.value)


def test_a_selection_failure_is_still_a_budget_error():
    """Callers that only care that the budget failed keep working."""
    assert issubclass(BudgetSelectionError, BudgetError)


def test_naming_one_of_several_resolves_it():
    derived = threshold_from(TWO, name="platform-monthly")
    assert derived.monthly == pytest.approx(200.0)


def test_a_single_budget_still_needs_no_name():
    one = {"budgets": [TWO["budgets"][0]]}
    assert threshold_from(one, name=None).monthly == pytest.approx(200.0)


def test_a_budget_that_cannot_yield_a_threshold_is_not_a_selection_failure():
    """This one still warns and falls back. It is data, not operator input."""
    unusable = {"budgets": [{"displayName": "only", "amount": {"lastPeriodAmount": {}}}]}
    with pytest.raises(BudgetError) as raised:
        threshold_from(unusable, name=None)

    assert not isinstance(raised.value, BudgetSelectionError)
