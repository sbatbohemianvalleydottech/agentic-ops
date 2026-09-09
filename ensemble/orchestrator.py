"""Gathers verdicts and hands them to the gate. Decides nothing itself."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from uuid import uuid4

from .gate import GateResult, evaluate_gate
from .providers import Provider
from .types import EvidenceBundle, Rubric


@dataclass(frozen=True)
class Rater:
    provider: Provider
    model: str


def run_decision(
    *,
    rubric: Rubric,
    evidence: EvidenceBundle,
    raters: list[Rater],
    judge: Rater,
    ledger,
    caller: str,
    decision_id: str | None = None,
) -> GateResult:
    """Run one gated decision.

    Raters are independent by definition, so they run concurrently. The judge
    depends on a candidate grade, so it runs after.

    The judge is called whether or not the raters agreed. Calling it only on
    agreement would make its cost conditional on an outcome and would hide
    regressions in the judge itself, so independence is kept structural rather
    than conventional. When raters disagree the gate halts on disagreement
    regardless, so the candidate grade cannot change the outcome.

    This function does not retry, reconcile or override anything. Principle V
    puts the next move with a human.
    """
    decision_id = decision_id or uuid4().hex

    with ThreadPoolExecutor(max_workers=len(raters)) as pool:
        calls = list(
            pool.map(
                lambda rater: rater.provider.grade(rubric, evidence, rater.model),
                raters,
            )
        )

    verdicts = []
    for rater, (verdict, usage) in zip(raters, calls, strict=True):
        ledger.record(
            decision_id=decision_id,
            caller=caller,
            model=rater.model,
            role="rater",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost=usage.cost,
        )
        verdicts.append(verdict)

    # Built before agreement is inspected. The first verdict present is the
    # candidate; nothing here looks at whether the grades match.
    candidate = next((v.grade for v in verdicts if v is not None), None)

    judge_verdict = None
    if candidate is not None:
        judge_verdict, usage = judge.provider.judge(
            rubric, evidence, candidate, judge.model
        )
        ledger.record(
            decision_id=decision_id,
            caller=caller,
            model=judge.model,
            role="judge",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost=usage.cost,
        )

    result = evaluate_gate(verdicts, judge_verdict, rubric)
    return replace(result, decision_id=decision_id)
