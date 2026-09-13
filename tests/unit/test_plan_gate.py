"""The gate: three conditions, and the environment decides what to do about them.

Staging blocks and production reports, which is deliberate and the opposite of
the obvious arrangement. Gate where a fix is still cheap. A cost tool standing in
front of an urgent production change does more damage than the change it objects
to, so there it reports and says what it would have done.
"""

from decimal import Decimal

from plan_cost.gate import decide
from plan_cost.rules import Finding

BLOCKING = Finding(
    rule="node_pool_without_autoscaling",
    severity="block",
    address="google_container_node_pool.primary",
    attribute="autoscaling",
    value="absent",
    why="capacity that can never be reclaimed",
)

REVIEW = Finding(
    rule="no_billing_labels",
    severity="review",
    address="google_compute_instance.web",
    attribute="labels",
    value="absent",
    why="spend that cannot be attributed",
)


def decision(*, findings=(BLOCKING,), total="400", policy="block"):
    return decide(
        findings=list(findings),
        total=Decimal(total),
        threshold=Decimal("250.00"),
        environment="staging" if policy == "block" else "production",
        environment_source="the plan",
        policy=policy,
    )


def test_all_three_conditions_in_staging_blocks():
    result = decision()
    assert result.blocked is True
    assert result.rule_fired == "node_pool_without_autoscaling"
    assert result.over_threshold is True


def test_the_same_change_in_production_reports_and_says_what_it_would_have_done():
    result = decision(policy="report")
    assert result.blocked is False
    assert result.would_have_blocked is True


def test_a_rule_fires_but_the_change_is_cheap():
    result = decision(total="12.40")
    assert result.blocked is False
    assert result.over_threshold is False
    assert result.rule_fired == "node_pool_without_autoscaling"


def test_an_expensive_change_with_only_review_findings_does_not_block():
    result = decision(findings=(REVIEW,), total="4000")
    assert result.blocked is False
    assert result.rule_fired is None
    assert result.over_threshold is True


def test_nothing_fired_and_nothing_expensive():
    result = decision(findings=(), total="10")
    assert result.blocked is False
    assert result.would_have_blocked is False


def test_a_change_that_removes_spend_never_blocks():
    result = decision(total="-900")
    assert result.blocked is False
    assert result.over_threshold is False


def test_exactly_at_the_threshold_does_not_block():
    """Over the line, not on it. A gate that fires on equality invites an
    argument about rounding instead of about the change."""
    result = decision(total="250.00")
    assert result.over_threshold is False
