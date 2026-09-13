"""Arguments, wiring and exit codes.

Exit 2 means the tool could not judge: an unreadable plan, a format version
nobody has checked, a contradictory price table, or no environment from either
source. It never means expensive. A gate that cannot tell a broken input from a
costly change is not usable in CI.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .gate import decide
from .plan import PlanError, load_plan
from .policy import Policy, PolicyError, action_for, load_policy, resolve_environment
from .prices import PriceError, PriceTable, load_prices
from .pricing import price_plan
from .report import render
from .rules import findings_for

HERE = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plan_cost",
        description="Price a Terraform plan, check it against deterministic rules, "
        "and gate on the result. No model calls, no network.",
    )
    parser.add_argument(
        "--plan", type=Path, help="a plan in JSON form, from `terraform show -json`"
    )
    parser.add_argument(
        "--env",
        dest="environment",
        help="the environment being changed. Falls back to the plan's "
        "variables.environment, and overrides it when both are present",
    )
    parser.add_argument("--prices", type=Path, default=HERE / "prices.toml")
    parser.add_argument("--policy", type=Path, default=HERE / "policy.toml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.plan is None:
        print("plan_cost: --plan is required", file=sys.stderr)
        return 2

    try:
        plan = load_plan(args.plan)
        table = load_prices(args.prices)
        policy = load_policy(args.policy)
        environment, source = resolve_environment(
            plan_environment=plan.environment, flag=args.environment
        )
        action = action_for(policy, environment)
    except (PlanError, PriceError, PolicyError) as exc:
        print(f"plan_cost: {exc}", file=sys.stderr)
        return 2

    priced = price_plan(plan.changes, table)
    findings = findings_for(plan.changes, policy.severities)
    decision = decide(
        findings=findings,
        total=priced.total,
        threshold=policy.threshold,
        environment=environment,
        environment_source=source,
        policy=action,
    )

    print(
        render(
            plan_path=args.plan,
            priced=priced,
            findings=findings,
            decision=decision,
            table=table,
            policy=policy,
        )
    )
    _warn_if_stale(table, policy)
    return 1 if decision.blocked else 0


def _warn_if_stale(table: PriceTable, policy: Policy) -> None:
    """Staleness goes to standard error, so the report stays clean when redirected."""
    if table.oldest is None:
        return
    age = (date.today() - table.oldest).days
    if age > policy.stale_after_days:
        print(
            f"plan_cost: the oldest price was taken {age} days ago, past the "
            f"{policy.stale_after_days} day limit in the policy. Refresh with "
            "--refresh-prices, or accept that these figures are old",
            file=sys.stderr,
        )
