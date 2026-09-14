"""The demo plans, and the exit codes somebody will quote in a meeting.

These exist so the demo cannot rot. If a rule, a rate or the gate changes and a
demo plan stops doing what its name says, this fails rather than the person
running it in front of an audience.
"""

from pathlib import Path

import pytest

from plan_cost.cli import main
from plan_cost.prices import load_prices

DEMO = Path(__file__).resolve().parents[2] / "plan_cost" / "fixtures" / "demo"
PRICES = DEMO / "prices.demo.toml"


def run(capsys, *args):
    code = main([str(arg) for arg in args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def judge(capsys, plan, *extra):
    return run(capsys, "--plan", DEMO / plan, "--prices", PRICES, *extra)


@pytest.mark.parametrize(
    "plan,expected",
    [
        ("staging-over-budget.json", 1),
        ("staging-normal.json", 0),
        ("production-over-budget.json", 0),
        ("production-normal.json", 0),
        ("incident-io-schedule.json", 0),
        ("staging-marginal.json", 0),
    ],
)
def test_each_demo_plan_exits_as_its_name_says(capsys, plan, expected):
    code, _, _ = judge(capsys, plan)
    assert code == expected


def test_only_staging_blocks_on_the_same_change(capsys):
    _, staging, _ = judge(capsys, "staging-over-budget.json")
    _, production, _ = judge(capsys, "production-over-budget.json")
    assert "+$1,222.60" in staging and "+$1,222.60" in production
    assert "DECISION  blocked" in staging
    assert "would have blocked in staging" in production


def test_an_expensive_but_clean_change_is_not_blocked(capsys):
    """Over the threshold with nothing fired. The gate needs both, and the
    report says which condition was missing."""
    code, out, _ = judge(capsys, "production-normal.json")
    assert code == 0
    assert "yes, +$270.10 over $250.00" in out
    assert "no, nothing fired at a blocking severity" in out


def test_the_european_worker_is_priced_at_the_european_rate(capsys):
    _, out, _ = judge(capsys, "production-normal.json")
    assert "+$160.60   1 x e2-standard-4, europe-west1" in out


def test_an_on_call_schedule_change_is_priced_at_nothing_rather_than_zero(capsys):
    code, out, _ = judge(capsys, "incident-io-schedule.json")
    assert code == 0
    assert "nothing here can be priced" in out
    assert "not a cloud resource 3" in out
    assert "$0.00" not in out


def test_a_plan_with_no_environment_is_an_error_not_a_pass(capsys):
    code, _, err = run(
        capsys, "--plan", DEMO / "incident-io-schedule-no-environment.json", "--prices", PRICES
    )
    assert code == 2
    assert "--env" in err and "variables" in err


def test_naming_the_environment_rescues_that_plan(capsys):
    code, _, _ = judge(capsys, "incident-io-schedule-no-environment.json", "--env", "staging")
    assert code == 0


def test_a_plan_where_everything_is_priced_prints_no_empty_not_counted_block(capsys):
    _, out, _ = judge(capsys, "staging-over-budget.json")
    assert "Not counted" not in out
    assert "3 resource changes, 3 accounted for" in out


def test_the_heading_names_the_rates_it_used_rather_than_calling_them_list_prices(capsys):
    """Running against the synthetic table, "list prices" would be a claim the
    table itself contradicts on every row."""
    _, out, _ = judge(capsys, "staging-normal.json")
    assert "prices.demo.toml" in out
    assert "list prices" not in out


def test_every_synthetic_rate_says_it_is_synthetic():
    for row in load_prices(PRICES).rows:
        assert "synthetic" in row.source


BUDGET = Path(__file__).resolve().parents[2] / "plan_cost" / "fixtures" / "budget" / "budgets.json"


def test_the_same_plan_passes_the_config_threshold_and_fails_your_budget(capsys):
    """The marginal plan sits between the two. $232.50 is under the $250 in
    policy.toml and over the $200 the budget's own alert line implies, so which
    threshold you use is the whole decision."""
    passes, config_out, _ = judge(capsys, "staging-marginal.json")
    blocks, budget_out, _ = judge(
        capsys, "staging-marginal.json",
        "--budget-json", BUDGET, "--budget-name", "platform-monthly",
    )
    assert passes == 0
    assert blocks == 1
    assert "+$232.50 at or under $250.00" in config_out
    assert "+$232.50 over $200.00" in budget_out


# Every documented way to reach exit 2 now ships a fixture. A cold reader with
# only the README found that two of the four were described and not runnable,
# so they had to take those on faith or fabricate input to check them.


def test_a_plan_format_this_tool_has_not_been_checked_against_refuses(capsys):
    code, out, err = run(
        capsys, "--plan", DEMO / "unchecked-format-version.json", "--prices", PRICES
    )
    assert code == 2
    assert "2.0" in err and "1.x" in err
    assert out == ""


def test_a_price_table_with_two_rows_for_one_key_refuses(capsys):
    code, out, err = run(
        capsys,
        "--plan", DEMO / "staging-normal.json",
        "--prices", DEMO / "prices.duplicate-row.toml",
    )
    assert code == 2
    assert "two rows carry the key" in err
    assert out == ""


def test_neither_refusal_prints_a_figure(capsys):
    """Exit 2 means could not judge. It must never look like a verdict."""
    for plan, prices in (
        ("unchecked-format-version.json", PRICES),
        ("staging-normal.json", DEMO / "prices.duplicate-row.toml"),
    ):
        _, out, _ = run(capsys, "--plan", DEMO / plan, "--prices", prices)
        assert "$" not in out
        assert "DECISION" not in out
