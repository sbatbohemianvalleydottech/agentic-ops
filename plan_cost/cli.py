"""Arguments, wiring and exit codes.

Exit 2 means the tool could not judge: an unreadable plan, a format version
nobody has checked, a contradictory price table, or no environment from either
source. It never means expensive. A gate that cannot tell a broken input from a
costly change is not usable in CI.

Two inputs come from the vendor, and both arrive as files the operator saved
with a documented command. Nothing here opens a socket.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ci import Exit

from .budget import BudgetError, BudgetSelectionError, threshold_from
from .gate import decide
from .plan import PlanError, load_plan
from .policy import Policy, PolicyError, action_for, load_policy, resolve_environment
from .prices import PriceError, PriceTable, load_prices
from .pricing import price_plan
from .refresh import RefreshError, refresh_prices
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
    parser.add_argument(
        "--budget-json",
        dest="budget",
        type=Path,
        help="saved output of `gcloud billing budgets list --format=json`. "
        "When given, the threshold comes from your budget rather than the policy file",
    )
    parser.add_argument(
        "--budget-name",
        dest="budget_name",
        help="which budget to use, when the response holds more than one",
    )
    parser.add_argument(
        "--refresh-prices",
        dest="refresh",
        type=Path,
        help="saved Cloud Billing Catalog response. Updates the price table and exits "
        "without judging a plan",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.refresh is not None:
        return _refresh(args)

    if args.plan is None:
        print("plan_cost: --plan is required", file=sys.stderr)
        return Exit.UNJUDGED

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
        return Exit.UNJUDGED

    threshold, threshold_note = _threshold(args, policy)
    if threshold is None:
        return Exit.UNJUDGED

    priced = price_plan(plan.changes, table)
    findings = findings_for(plan.changes, policy.severities)
    decision = decide(
        findings=findings,
        total=priced.total,
        threshold=threshold,
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
            prices_path=args.prices,
            threshold_note=threshold_note,
        )
    )
    _warn_if_stale(table, policy)
    return Exit.BLOCKED if decision.blocked else Exit.OK


def _threshold(args: argparse.Namespace, policy: Policy):
    """The monthly limit, and the note explaining where it came from.

    A budget that cannot produce one is a warning and a fallback, never a guess.
    A budget the operator failed to identify is neither: it refuses, because
    falling back would judge the plan against a threshold nobody asked for.
    """
    if args.budget is None:
        return policy.threshold, ""
    try:
        document = json.loads(args.budget.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"plan_cost: {args.budget} could not be read: {exc}", file=sys.stderr)
        return None, ""
    try:
        derived = threshold_from(document, name=args.budget_name)
    except BudgetSelectionError as exc:
        print(f"plan_cost: {exc}", file=sys.stderr)
        return None, ""
    except BudgetError as exc:
        print(
            f"plan_cost: {exc}. Falling back to the threshold in the policy file",
            file=sys.stderr,
        )
        return policy.threshold, f"budget not used: {exc}"
    return derived.monthly, (
        f"{derived.derivation}. It covers {derived.applies_to}, "
        "which was not matched against this plan"
    )


def _refresh(args: argparse.Namespace) -> int:
    try:
        catalogue = json.loads(args.refresh.read_text(encoding="utf-8"))
        report = refresh_prices(args.prices, catalogue, today=date.today())
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"plan_cost: {args.refresh} could not be read as a catalogue response: {exc}",
            file=sys.stderr,
        )
        return Exit.UNJUDGED
    except RefreshError as exc:
        print(f"plan_cost: {exc}", file=sys.stderr)
        return Exit.UNJUDGED

    print(f"PRICE REFRESH  {args.prices}")
    print()
    print(report.as_text())
    return Exit.OK


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
