"""Policy, and which environment is being judged.

The last test is the important one. A missing environment must never resolve to
the lenient path, because a gate that silently became a report is worse than no
gate: everyone believes it is running.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from plan_cost.policy import PolicyError, action_for, load_policy, resolve_environment

SHIPPED = Path(__file__).resolve().parents[2] / "plan_cost" / "policy.toml"


def test_the_shipped_policy_loads():
    policy = load_policy(SHIPPED)
    assert policy.threshold == Decimal("250.00")
    assert policy.stale_after_days == 90


def test_staging_blocks_and_production_reports():
    policy = load_policy(SHIPPED)
    assert action_for(policy, "staging") == "block"
    assert action_for(policy, "production") == "report"


def test_an_environment_nobody_configured_is_an_error_naming_the_ones_that_are():
    policy = load_policy(SHIPPED)
    with pytest.raises(PolicyError) as raised:
        action_for(policy, "sandbox")
    assert "staging" in str(raised.value) and "production" in str(raised.value)


def test_severities_come_from_the_file():
    policy = load_policy(SHIPPED)
    assert policy.severities["node_pool_without_autoscaling"] == "block"
    assert policy.severities["no_billing_labels"] == "review"


def test_the_environment_comes_from_the_plan_when_it_carries_one():
    name, source = resolve_environment(plan_environment="staging", flag=None)
    assert name == "staging"
    assert "plan" in source


def test_the_flag_is_used_when_the_plan_carries_nothing():
    name, source = resolve_environment(plan_environment=None, flag="production")
    assert name == "production"
    assert "--env" in source


def test_the_flag_overrides_the_plan_and_says_what_it_overrode():
    name, source = resolve_environment(plan_environment="production", flag="staging")
    assert name == "staging"
    assert "production" in source and "--env" in source


def test_neither_source_is_an_error_naming_both_ways_to_fix_it():
    with pytest.raises(PolicyError) as raised:
        resolve_environment(plan_environment=None, flag=None)
    message = str(raised.value)
    assert "--env" in message and "variables" in message
