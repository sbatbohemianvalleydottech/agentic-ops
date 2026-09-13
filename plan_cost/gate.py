"""Three conditions, and what the environment does about them.

Blocking needs all three: a rule fired at a blocking severity, the monthly
change is over the threshold, and this environment blocks. Staging blocks and
production reports, deliberately. Gate where a fix is still cheap; a cost tool
standing in front of an urgent production change does more harm than the change
it objects to, so there it reports and says what it would have done.

The decision carries all three conditions whether it blocked or not, so the
report can always name the one that was not met.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .rules import Finding


@dataclass(frozen=True)
class Decision:
    environment: str
    environment_source: str
    policy: str
    rule_fired: str | None
    total: Decimal
    threshold: Decimal
    over_threshold: bool
    blocked: bool
    would_have_blocked: bool


def decide(
    *,
    findings: Sequence[Finding],
    total: Decimal,
    threshold: Decimal,
    environment: str,
    environment_source: str,
    policy: str,
) -> Decision:
    rule_fired = next((f.rule for f in findings if f.severity == "block"), None)
    # Over the line, not on it. A gate that fires on equality starts an argument
    # about rounding instead of about the change.
    over_threshold = total > threshold
    conditions_met = rule_fired is not None and over_threshold
    blocked = conditions_met and policy == "block"
    return Decision(
        environment=environment,
        environment_source=environment_source,
        policy=policy,
        rule_fired=rule_fired,
        total=total,
        threshold=threshold,
        over_threshold=over_threshold,
        blocked=blocked,
        would_have_blocked=conditions_met and not blocked,
    )
