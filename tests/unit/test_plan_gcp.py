"""The Cloud Billing APIs represent money as units plus nanos.

Two readers needed that conversion and each grew its own copy, with its own
NANOS constant and its own function called `_money`. A third function in the
same package, also called `money`, formats a Decimal for display. One name,
two jobs, three definitions.
"""

from decimal import Decimal

import pytest

from plan_cost.gcp import NANOS, money_from_api


def test_units_alone():
    assert money_from_api({"units": "800"}) == Decimal("800")


def test_nanos_alone():
    assert money_from_api({"nanos": 500_000_000}) == Decimal("0.5")


def test_units_and_nanos_together():
    assert money_from_api({"units": "12", "nanos": 250_000_000}) == Decimal("12.25")


def test_an_absent_field_is_zero_rather_than_an_error():
    assert money_from_api({}) == Decimal("0")


def test_an_explicit_null_is_zero_too():
    """The API omits a field or sends null for it, and both mean nothing."""
    assert money_from_api({"units": None, "nanos": None}) == Decimal("0")


def test_the_result_is_exact_rather_than_a_float():
    """A price that has passed through a float cannot be trusted to sum."""
    value = money_from_api({"units": "0", "nanos": 21_000_000})
    assert value == Decimal("0.021")
    assert isinstance(value, Decimal)


def test_nanos_scale_is_the_documented_billion():
    assert NANOS == Decimal(1_000_000_000)


@pytest.mark.parametrize("reader", ["plan_cost.budget", "plan_cost.refresh"])
def test_both_readers_use_the_shared_conversion(reader):
    """If either grows its own copy again, this fails."""
    import importlib

    module = importlib.import_module(reader)
    assert module.money_from_api is money_from_api
    assert not hasattr(module, "_money"), (
        f"{reader} has its own _money again; the shared one is plan_cost.gcp"
    )
