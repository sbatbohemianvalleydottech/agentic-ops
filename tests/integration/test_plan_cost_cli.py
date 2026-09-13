"""End to end, against the two fixtures.

The SaaS fixture is the one that matters most. A tool that prices its own
estate fixture and nothing else would pass every test here and be worthless in
front of a plan it has not seen.
"""

import re
from pathlib import Path

from plan_cost.cli import main

REPO = Path(__file__).resolve().parents[2]
ESTATE = REPO / "plan_cost" / "fixtures" / "estate" / "plan.json"
SAAS = REPO / "plan_cost" / "fixtures" / "saas" / "plan.json"


def run(capsys, *args):
    code = main([str(arg) for arg in args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_the_estate_blocks_in_staging(capsys):
    code, out, _ = run(capsys, "--plan", ESTATE, "--env", "staging")
    assert code == 1
    assert "blocked" in out
    assert "node_pool_without_autoscaling" in out


def test_the_monthly_total_is_the_sum_of_the_priced_lines(capsys):
    _, out, _ = run(capsys, "--plan", ESTATE, "--env", "staging")
    assert "+$432.89" in out


def test_every_changed_resource_is_accounted_for(capsys):
    _, out, _ = run(capsys, "--plan", ESTATE, "--env", "staging")
    assert "12 resource changes, 12 accounted for" in out


def test_what_could_not_be_priced_is_named(capsys):
    _, out, _ = run(capsys, "--plan", ESTATE, "--env", "staging")
    assert "unknown until apply" in out
    assert "no price row" in out
    assert "not priceable" in out


def test_the_same_plan_in_production_reports_instead(capsys):
    code, out, _ = run(capsys, "--plan", ESTATE, "--env", "production")
    assert code == 0
    assert "would have blocked in staging" in out
    assert "+$432.89" in out


def test_the_environment_is_taken_from_the_plan_when_no_flag_is_given(capsys):
    code, out, _ = run(capsys, "--plan", ESTATE)
    assert code == 1
    assert "variables.environment" in out


def test_a_flag_overriding_the_plan_says_so(capsys):
    _, out, _ = run(capsys, "--plan", ESTATE, "--env", "production")
    assert "staging" in out and "--env" in out


def test_nothing_in_the_saas_plan_is_priceable(capsys):
    code, out, _ = run(capsys, "--plan", SAAS, "--env", "staging")
    assert code == 0
    assert re.search(r"not priceable\s+5\s+not a cloud resource 5", out)


def test_the_saas_plan_claims_no_figure_at_all(capsys):
    _, out, _ = run(capsys, "--plan", SAAS, "--env", "staging")
    assert "$0.00" not in out
    assert "nothing here can be priced" in out


def test_a_plan_with_no_environment_anywhere_is_a_usage_error(capsys, tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text('{"format_version": "1.2", "resource_changes": []}', encoding="utf-8")
    code, _, err = run(capsys, "--plan", plan)
    assert code == 2
    assert "--env" in err and "variables" in err


def test_an_unreadable_plan_is_a_usage_error_not_an_expensive_one(capsys, tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text('{"format_version": "9.0", "resource_changes": []}', encoding="utf-8")
    code, _, err = run(capsys, "--plan", plan, "--env", "staging")
    assert code == 2
    assert "9.0" in err


def test_the_report_is_on_stdout_and_warnings_are_not(capsys):
    _, out, err = run(capsys, "--plan", ESTATE, "--env", "staging")
    assert "PLAN COST" in out
    assert "PLAN COST" not in err
