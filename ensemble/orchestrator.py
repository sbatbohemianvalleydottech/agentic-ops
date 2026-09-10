"""Gathers verdicts and hands them to the gate. Decides nothing itself."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from uuid import uuid4

from .gate import GateResult, evaluate_gate
from .progress import Progress, SilentProgress
from .providers import Call, Provider
from .types import EvidenceBundle, Rubric


@dataclass(frozen=True)
class Rater:
    provider: Provider
    model: str


@dataclass(frozen=True)
class Failure:
    """A call that produced no verdict, and why. Travels into the gate result so
    a halt can say what actually went wrong rather than blaming disagreement."""

    model: str
    role: str
    reason: str


def run_decision(
    *,
    rubric: Rubric,
    evidence: EvidenceBundle,
    raters: list[Rater],
    judge: Rater,
    ledger,
    caller: str,
    decision_id: str | None = None,
    progress: Progress | None = None,
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
    progress = progress or SilentProgress()
    failures: list[Failure] = []

    def meter(model: str, role: str, call: Call) -> None:
        ledger.record(
            decision_id=decision_id,
            caller=caller,
            model=model,
            role=role,
            input_tokens=call.usage.input_tokens,
            output_tokens=call.usage.output_tokens,
            cost=call.usage.cost,
            rubric=rubric.name,
        )
        if call.failed:
            failures.append(
                Failure(model=model, role=role, reason=call.error or "no reason given")
            )
        progress.step(
            f"{rubric.name}: {role} {model}{' FAILED' if call.failed else ''}",
            call.usage.cost,
        )

    with ThreadPoolExecutor(max_workers=len(raters)) as pool:
        calls = list(
            pool.map(
                lambda rater: rater.provider.grade(rubric, evidence, rater.model),
                raters,
            )
        )

    verdicts = []
    for rater, call in zip(raters, calls, strict=True):
        meter(rater.model, "rater", call)
        verdicts.append(call.verdict)

    # Built before agreement is inspected. The first verdict present is the
    # candidate; nothing here looks at whether the grades match.
    candidate = next((v.grade for v in verdicts if v is not None), None)

    judge_verdict = None
    if candidate is not None:
        judge_call = judge.provider.judge(rubric, evidence, candidate, judge.model)
        meter(judge.model, "judge", judge_call)
        judge_verdict = judge_call.verdict

    result = evaluate_gate(verdicts, judge_verdict, rubric)
    return replace(result, decision_id=decision_id, failures=tuple(failures))
