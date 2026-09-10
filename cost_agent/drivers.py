"""Group findings into structural drivers and attribute every dollar exactly once.

The attribution rule is the part a sceptical reader will attack, so it is one
explicit ordering rather than a heuristic: eliminate, then retain less, then
resize, then renegotiate. Each remedy subsumes the ones below it, so a resource
matching several is attributed to the highest and the alternative is recorded.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from .classify import Finding, RootCause, Rule
from .inputs import Inputs, Unmatched
from .thresholds import Thresholds

CENTS = Decimal("0.01")

# What is missing, not what is expensive. "Node pools are sized once and never
# revisited" explains six lines at once; "GKE is expensive" explains none.
ABSENT_PRACTICE = {
    RootCause.WORKLOAD_ELIMINATION: (
        "Nothing decommissions resources when the workload behind them goes away, "
        "so the estate only ever grows."
    ),
    RootCause.RETENTION_LIFECYCLE: (
        "No lifecycle policy moves or expires data, so storage class is decided "
        "once at creation and never revisited."
    ),
    RootCause.CAPACITY_MANAGEMENT: (
        "Capacity is provisioned for peak at creation and never revisited, because "
        "nobody owns it after the resource exists."
    ),
    RootCause.COMMERCIAL: (
        "Spend has no owner and no commitment strategy, so nothing is negotiated "
        "and nobody is accountable for the bill."
    ),
}


@dataclass(frozen=True)
class Driver:
    root_cause: RootCause
    absent_practice: str
    cloud: str
    findings: tuple[Finding, ...]
    annual_cost: Decimal
    share_of_bill: Decimal
    single_resource: bool
    savings_low: Decimal = Decimal("0")
    savings_high: Decimal = Decimal("0")
    savings_pct_low: Decimal = Decimal("0")
    savings_pct_high: Decimal = Decimal("0")
    confidence: str = "unrated"
    what_would_change_confidence: str = ""
    confirming_question: str = ""


@dataclass(frozen=True)
class ContestedAttribution:
    resource_id: str
    assigned_to: RootCause
    also_matched: tuple[RootCause, ...]
    basis: str


@dataclass(frozen=True)
class Analysis:
    total_bill_annual: Decimal
    annualisation_multiplier: Decimal
    drivers: tuple[Driver, ...] = ()
    contested: tuple[ContestedAttribution, ...] = ()
    unassessable: tuple[Finding, ...] = ()
    unmatched: tuple[Unmatched, ...] = ()
    healthy: tuple[str, ...] = ()
    # Every resource from either input. Used to assert nothing was dropped.
    resource_count: int = 0
    findings_by_resource: dict = field(default_factory=dict)


def build_analysis(
    findings: list[Finding], inputs: Inputs, thresholds: Thresholds
) -> Analysis:
    multiplier = thresholds.annualisation_multiplier
    cost_of = {r.resource_id: r.period_cost for r in inputs.matched}
    cloud_of = {r.resource_id: r.cloud for r in inputs.matched}

    by_resource: dict[str, list[Finding]] = {}
    for finding in findings:
        by_resource.setdefault(finding.resource_id, []).append(finding)

    unassessable = tuple(f for f in findings if f.rule is Rule.UNASSESSABLE)
    unassessable_ids = {f.resource_id for f in unassessable}

    owned: dict[RootCause, list[Finding]] = {}
    contested: list[ContestedAttribution] = []
    healthy: list[str] = []

    for resource_id in cost_of:
        candidates = [
            f for f in by_resource.get(resource_id, []) if f.root_cause is not None
        ]
        if not candidates:
            # Unassessable resources are reported separately; anything else with
            # no finding is genuinely healthy and still has to be accounted for.
            if resource_id not in unassessable_ids:
                healthy.append(resource_id)
            continue

        matched = {f.root_cause for f in candidates}
        winner = min(matched, key=lambda cause: cause.value)

        # Only findings under the winning cause travel with the driver, so the
        # dollars cannot be claimed twice.
        owned.setdefault(winner, []).extend(
            f for f in candidates if f.root_cause is winner
        )

        if len(matched) > 1:
            beaten = tuple(sorted(matched - {winner}, key=lambda cause: cause.value))
            contested.append(
                ContestedAttribution(
                    resource_id=resource_id,
                    assigned_to=winner,
                    also_matched=beaten,
                    basis=(
                        f"{winner.name} outranks "
                        f"{', '.join(cause.name for cause in beaten)}: its remedy "
                        "makes the others moot, so counting both would overstate "
                        "what is available."
                    ),
                )
            )

    total_annual = (inputs.total_period_cost * multiplier).quantize(CENTS)

    drivers = []
    for root_cause, cause_findings in owned.items():
        resource_ids = {f.resource_id for f in cause_findings}
        annual = (
            sum((cost_of[r] for r in resource_ids), Decimal("0")) * multiplier
        ).quantize(CENTS)
        clouds = {cloud_of[r] for r in resource_ids}

        drivers.append(
            Driver(
                root_cause=root_cause,
                absent_practice=ABSENT_PRACTICE[root_cause],
                cloud=clouds.pop() if len(clouds) == 1 else "multiple",
                findings=tuple(cause_findings),
                annual_cost=annual,
                share_of_bill=(
                    (annual / total_annual).quantize(Decimal("0.0001"))
                    if total_annual
                    else Decimal("0")
                ),
                single_resource=len(resource_ids) == 1,
            )
        )

    drivers.sort(key=lambda d: d.annual_cost, reverse=True)

    return Analysis(
        total_bill_annual=total_annual,
        annualisation_multiplier=multiplier,
        drivers=tuple(drivers),
        contested=tuple(contested),
        unassessable=unassessable,
        unmatched=inputs.unmatched,
        healthy=tuple(healthy),
        resource_count=len(inputs.matched) + len(inputs.unmatched),
        findings_by_resource=by_resource,
    )
