"""What blocks, where, and which environment is being judged.

The last function is the one that matters. A missing environment is an error,
never a default, because a gate that silently became a report is worse than no
gate at all: everybody carries on believing it runs.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


class PolicyError(Exception):
    """The policy or the environment cannot be resolved. Never guessed."""


@dataclass(frozen=True)
class Policy:
    threshold: Decimal
    environments: dict[str, str]
    severities: dict[str, str]
    stale_after_days: int


def load_policy(path: Path) -> Policy:
    try:
        document = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PolicyError(f"{path} could not be read as a policy: {exc}") from exc

    raw_threshold = document.get("gate", {}).get("threshold_usd_month")
    if raw_threshold is None:
        raise PolicyError(f"{path} sets no gate.threshold_usd_month")
    if isinstance(raw_threshold, float):
        raise PolicyError("quote the threshold as a string so it stays an exact decimal")
    try:
        threshold = Decimal(str(raw_threshold))
    except InvalidOperation:
        raise PolicyError(f"the threshold is not a number: {raw_threshold!r}") from None

    environments = {str(k): str(v) for k, v in (document.get("environments") or {}).items()}
    if not environments:
        raise PolicyError(f"{path} configures no environments, so nothing can be judged")
    unknown = {name: action for name, action in environments.items()
               if action not in ("block", "report")}
    if unknown:
        raise PolicyError(f"environments must be block or report, not {unknown}")

    return Policy(
        threshold=threshold,
        environments=environments,
        severities={str(k): str(v) for k, v in (document.get("rules") or {}).items()},
        stale_after_days=int((document.get("prices") or {}).get("stale_after_days", 90)),
    )


def action_for(policy: Policy, environment: str) -> str:
    try:
        return policy.environments[environment]
    except KeyError:
        configured = ", ".join(sorted(policy.environments))
        raise PolicyError(
            f"no policy for environment {environment!r}; the policy configures {configured}"
        ) from None


def resolve_environment(*, plan_environment: str | None, flag: str | None) -> tuple[str, str]:
    """The environment being judged, and where that came from.

    Both are reported, because a reader needs to know whether the gate judged
    what they think it judged.
    """
    if flag and plan_environment and flag != plan_environment:
        return flag, f"the --env flag, overriding {plan_environment} from the plan"
    if flag and plan_environment:
        return flag, "the --env flag, matching the plan"
    if flag:
        return flag, "the --env flag"
    if plan_environment:
        return plan_environment, "the plan's variables.environment"
    raise PolicyError(
        "no environment to judge: the plan carries no variables.environment, "
        "and no --env was given. This is not defaulted, because a gate that "
        "quietly became a report is worse than no gate"
    )
