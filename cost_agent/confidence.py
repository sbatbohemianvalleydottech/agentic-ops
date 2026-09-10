"""Rate each driver's confidence through the halt gate.

The only part of this package that spends money, which is why it is optional and
why everything a sceptical reader checks runs without it.

A savings estimate with no confidence is a guess presented as a finding. A
confidence that averages two disagreeing assessments is worse: it is a fabricated
agreement wearing a number. So a split marks the driver for review and says so.
"""

from dataclasses import replace
from datetime import datetime

from ensemble.explain import explain
from ensemble.gate import Decision
from ensemble.orchestrator import Rater, run_decision
from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric

from .drivers import Driver

CONFIDENCE_RUBRIC = Rubric(
    name="savings_confidence",
    criteria=(
        "How much confidence does this evidence support in the savings estimate for "
        "this cost driver? Weigh how directly the observed values demonstrate "
        "recoverable slack. Utilisation averages can hide peaks, and a resource that "
        "looks idle may be a warm standby. Rate the evidence, not the size of the "
        "number."
    ),
    scale=("low", "medium", "high"),
)


def _evidence(driver: Driver, as_of: datetime) -> EvidenceBundle:
    """One record per finding, so every assessment cites the basis it rests on."""
    return EvidenceBundle(
        subject=f"{driver.root_cause.name} driver, {driver.cloud}, "
        f"{driver.annual_cost} annual",
        records=tuple(
            EvidenceRecord(
                source="classifier",
                timestamp=as_of,
                ref=f"{finding.resource_id}:{finding.rule.value}",
                content=(
                    f"{finding.rule.value} on {finding.resource_id}; "
                    f"observed {finding.observed}; "
                    f"recoverable fraction {finding.recoverable_fraction}"
                ),
            )
            for finding in driver.findings
        ),
    )


def rate_confidence(
    driver: Driver,
    *,
    raters: list[Rater],
    judge: Rater,
    ledger,
    as_of: datetime,
    progress=None,
) -> Driver:
    result = run_decision(
        rubric=CONFIDENCE_RUBRIC,
        evidence=_evidence(driver, as_of),
        raters=raters,
        judge=judge,
        ledger=ledger,
        caller="cost_agent",
        progress=progress,
    )

    if result.decision is not Decision.PROCEED:
        # Deliberately not resolved to a middle value. The split is the finding.
        return replace(
            driver,
            confidence="NEEDS_REVIEW",
            confidence_raters=result.raters,
            what_would_change_confidence=(
                f"{driver.what_would_change_confidence} "
                f"{explain(result)} A human should look before this driver is "
                "relied on."
            ),
        )

    # The reasoning travels with the rating. A confidence figure whose basis was
    # dropped on the way to the report is the same unsupported claim this
    # repository exists to argue against.
    return replace(driver, confidence=result.grade, confidence_raters=result.raters)
