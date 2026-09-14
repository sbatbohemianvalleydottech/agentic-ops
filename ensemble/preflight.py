"""One cheap call per configured model, before anything expensive runs.

Reachability is only discoverable by calling. A registry lookup passed for a
model the API then rejected, which is exactly why this makes a real request
rather than consulting a table.

No retries. A 503 at preflight is information about right now, and hiding it
behind a retry would restore the silence this exists to remove.
"""

from dataclasses import dataclass
from decimal import Decimal

from .providers import call_cost, redact

# A handful of tokens. Enough to prove the model answers, not enough to matter.
PROBE_PROMPT = "Reply with the single word: ok"
PROBE_MAX_TOKENS = 8


@dataclass(frozen=True)
class ModelCheck:
    model: str
    reachable: bool
    reason: str | None
    cost: float
    # Recorded alongside the cost so a probe row in the ledger is the same
    # shape as every other row rather than a special case.
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class PreflightResult:
    checks: tuple[ModelCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.reachable for check in self.checks)

    @property
    def total_cost(self) -> Decimal:
        return sum((Decimal(str(check.cost)) for check in self.checks), Decimal("0"))

    def render(self) -> str:
        lines = ["Preflight:"]
        for check in self.checks:
            if check.reachable:
                lines.append(f"  ok    {check.model}")
            else:
                lines += [f"  FAIL  {check.model}", f"          {check.reason}"]
        lines.append(f"  cost  ${self.total_cost:.5f}")
        return "\n".join(lines)


def _live_probe(model: str) -> ModelCheck:
    from litellm import completion

    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": PROBE_PROMPT}],
            max_tokens=PROBE_MAX_TOKENS,
        )
    except Exception as error:
        return ModelCheck(
            model=model,
            reachable=False,
            reason=redact(f"{type(error).__name__}: {' '.join(str(error).split())}"),
            cost=0.0,
        )

    usage = getattr(response, "usage", None)
    return ModelCheck(
        model=model,
        reachable=True,
        reason=None,
        cost=call_cost(response),
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )


def preflight(
    models: list[str], probe=None, *, ledger=None, caller: str = "preflight"
) -> PreflightResult:
    """Probe each distinct model once, preserving the order first seen.

    Deduplicated because a rater and a judge frequently share a model, and
    paying twice to learn the same thing is the sort of waste this repository
    keeps complaining about elsewhere.

    Every probe is a real call to a real vendor, so every probe is metered when
    a ledger is given, failures included. They land under the decision id
    "preflight", which makes lifetime probe spend one lookup rather than an
    absence nobody notices.
    """
    probe = probe or _live_probe

    seen: dict[str, ModelCheck] = {}
    for model in models:
        if model not in seen:
            check = probe(model)
            if ledger is not None:
                ledger.record(
                    decision_id="preflight",
                    caller=caller,
                    model=check.model,
                    role="probe",
                    input_tokens=check.input_tokens,
                    output_tokens=check.output_tokens,
                    cost=check.cost,
                )
            seen[model] = (
                check
                if check.reason is None
                else ModelCheck(
                    model=check.model,
                    reachable=check.reachable,
                    reason=redact(check.reason),
                    cost=check.cost,
                )
            )

    return PreflightResult(checks=tuple(seen.values()))
