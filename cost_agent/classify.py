"""Turn observable properties into findings.

Pure. Given the same inputs, thresholds and analysis date, always the same
findings. `as_of` is a parameter rather than a call to the clock, because a
classifier that reads the time cannot be reproduced by the person checking it.

No rule may branch on `service`, `cloud` or any product name. That is the whole
difference between analysing an estate and recognising a fixture, and there is a
test asserting it.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from .inputs import Inputs, Resource
from .thresholds import Thresholds


class RootCause(Enum):
    """Ordered. Each level's remedy subsumes every level below it, so a resource
    matching several is attributed to the highest. Right-sizing something you are
    about to delete is wasted work, and counting both overstates what is
    available."""

    WORKLOAD_ELIMINATION = 1
    RETENTION_LIFECYCLE = 2
    CAPACITY_MANAGEMENT = 3
    COMMERCIAL = 4


class Rule(Enum):
    SCHEDULED_DECOMMISSION = "scheduled_decommission"
    OVERDUE_DECOMMISSION = "overdue_decommission"
    STALE_UNATTACHED = "stale_unattached"
    COLD_ON_HOT_TIER = "cold_on_hot_tier"
    IDLE = "idle"
    UNDER_UTILISED = "under_utilised"
    OVERSIZED = "oversized"
    PEAK_SHAPED_ALWAYS_ON = "peak_shaped_always_on"
    NO_COMMITMENT = "no_commitment"
    UNTAGGED = "untagged"
    UNASSESSABLE = "unassessable"


ROOT_CAUSE_OF = {
    Rule.SCHEDULED_DECOMMISSION: RootCause.WORKLOAD_ELIMINATION,
    Rule.OVERDUE_DECOMMISSION: RootCause.WORKLOAD_ELIMINATION,
    Rule.STALE_UNATTACHED: RootCause.WORKLOAD_ELIMINATION,
    Rule.COLD_ON_HOT_TIER: RootCause.RETENTION_LIFECYCLE,
    Rule.IDLE: RootCause.CAPACITY_MANAGEMENT,
    Rule.UNDER_UTILISED: RootCause.CAPACITY_MANAGEMENT,
    Rule.OVERSIZED: RootCause.CAPACITY_MANAGEMENT,
    Rule.PEAK_SHAPED_ALWAYS_ON: RootCause.CAPACITY_MANAGEMENT,
    Rule.NO_COMMITMENT: RootCause.COMMERCIAL,
    Rule.UNTAGGED: RootCause.COMMERCIAL,
}

HOT_TIERS = {"standard", "hot", "premium"}

# Share of a resource's cost each rule considers addressable. Deliberately
# conservative: these feed the lower bound of a savings range that someone will
# be asked to believe.
RECOVERABLE = {
    # The spend ends when the workload does. Realised at the horizon, not now,
    # which is why the driver reports the date alongside the figure.
    Rule.SCHEDULED_DECOMMISSION: Decimal("1.00"),
    Rule.OVERDUE_DECOMMISSION: Decimal("1.00"),
    Rule.STALE_UNATTACHED: Decimal("1.00"),
    Rule.COLD_ON_HOT_TIER: Decimal("0.60"),
    Rule.IDLE: Decimal("0.80"),
    Rule.UNDER_UTILISED: Decimal("0.30"),
    Rule.OVERSIZED: Decimal("0.25"),
    Rule.PEAK_SHAPED_ALWAYS_ON: Decimal("0.25"),
    Rule.NO_COMMITMENT: Decimal("0.20"),
    Rule.UNTAGGED: Decimal("0.00"),
}


@dataclass(frozen=True)
class Finding:
    resource_id: str
    rule: Rule
    observed: dict
    recoverable_fraction: Decimal

    @property
    def root_cause(self) -> RootCause | None:
        return ROOT_CAUSE_OF.get(self.rule)


@dataclass(frozen=True)
class Gap:
    """A rule that could not run on a resource, and the field it needed.

    Recorded by the classifier at the branch that decides the rule cannot run,
    rather than derived from a table of rules and their inputs. A table would be
    a second statement of the conditions below and would drift from them the
    first time a rule changed.

    Distinct from a finding of `UNASSESSABLE`, which says a resource could not be
    judged at all. This says one check could not run, and the resource may still
    have been judged by every other check.
    """

    resource_id: str
    rule: Rule
    field: str


def _needs_utilisation(resource: Resource) -> bool:
    return resource.kind in {"compute", "database", "cache", "queue"}


def _has_tiers(resource: Resource) -> bool:
    """Whether a storage class is a thing this kind of resource even has.

    A virtual machine has no hot or cold tier, so reporting `cold_on_hot_tier`
    as unable to run on one would be noise, and a report full of inapplicable
    checks is the report people learn to skip. Same shape and same reason as
    `_needs_utilisation` above: `kind`, never a service or product name.
    """
    return resource.kind == "storage"


def _finding(resource: Resource, rule: Rule, **observed) -> Finding:
    return Finding(
        resource_id=resource.resource_id,
        rule=rule,
        observed=observed,
        recoverable_fraction=RECOVERABLE.get(rule, Decimal("0.00")),
    )


def _classify_one(
    resource: Resource, thresholds: Thresholds, as_of: datetime
) -> tuple[list[Finding], list[Gap]]:
    findings: list[Finding] = []
    gaps: list[Gap] = []

    def gap(rule: Rule, field: str) -> None:
        gaps.append(Gap(resource_id=resource.resource_id, rule=rule, field=field))

    if resource.decommission_at is not None:
        remaining = (resource.decommission_at - as_of).days
        # Split deliberately. Still being billed for something that should already
        # be gone is a stronger finding than a planned retirement, and one rule
        # covering both would hide it inside the weaker case.
        rule = (
            Rule.SCHEDULED_DECOMMISSION if remaining >= 0 else Rule.OVERDUE_DECOMMISSION
        )
        defect_field = "days_remaining" if remaining >= 0 else "days_overdue"
        findings.append(
            _finding(
                resource,
                rule,
                decommission_at=f"{resource.decommission_at:%Y-%m-%d}",
                **{defect_field: abs(remaining)},
            )
        )

    if not resource.attached and resource.age_days > thresholds.stale_after_days:
        findings.append(
            _finding(resource, Rule.STALE_UNATTACHED,
                     attached=False, age_days=resource.age_days)
        )

    if resource.tier is None:
        # Nothing is known about where the data sits, so the rule never got as
        # far as asking how long since it was read. Only a gap where a tier is
        # a property the resource could have had.
        if _has_tiers(resource):
            gap(Rule.COLD_ON_HOT_TIER, "tier")
    elif resource.tier in HOT_TIERS and resource.last_access is None:
        gap(Rule.COLD_ON_HOT_TIER, "last_access")
    elif (
        resource.tier in HOT_TIERS
        and (as_of - resource.last_access).days > thresholds.cold_after_days
    ):
        findings.append(
            _finding(resource, Rule.COLD_ON_HOT_TIER, tier=resource.tier,
                     days_since_access=(as_of - resource.last_access).days)
        )
    # A tier that is present and not hot is not a gap. The rule ran, and the
    # answer was no.

    utilisation = resource.utilisation_avg

    if utilisation is None and _needs_utilisation(resource):
        # One absent field stops three rules. Recorded per rule, because "idle
        # could not run" is what a reader needs, not "a field was missing".
        # A bucket has no utilisation to be missing, so this is only a gap where
        # the number was expected.
        for rule in (Rule.IDLE, Rule.UNDER_UTILISED, Rule.NO_COMMITMENT):
            gap(rule, "utilisation_avg")

    if utilisation is None and _needs_utilisation(resource):
        # Cannot be called under-utilised on absent evidence, and must not be
        # quietly counted as healthy either.
        findings.append(_finding(resource, Rule.UNASSESSABLE, utilisation_avg=None))
    elif utilisation is not None:
        if utilisation <= thresholds.idle_ceiling:
            findings.append(
                _finding(resource, Rule.IDLE, utilisation_avg=utilisation)
            )
        elif utilisation < thresholds.target_floor:
            findings.append(
                _finding(resource, Rule.UNDER_UTILISED, utilisation_avg=utilisation)
            )

        if not resource.commitment_covered and utilisation >= thresholds.target_floor:
            # Only steady usage is a commitment candidate. Committing to capacity
            # you should be shrinking locks in the waste.
            findings.append(
                _finding(resource, Rule.NO_COMMITMENT, utilisation_avg=utilisation,
                         commitment_covered=False)
            )

    # Both read capacity numbers, which only a resource that runs a workload
    # has. On a bucket their absence is the shape of the thing, not a gap.
    if _needs_utilisation(resource):
        for rule, pair in (
            (Rule.OVERSIZED, ("provisioned", "observed_peak")),
            (Rule.PEAK_SHAPED_ALWAYS_ON, ("weekday_utilisation", "weekend_utilisation")),
        ):
            for field in pair:
                if getattr(resource, field) is None:
                    gap(rule, field)

    if resource.provisioned and resource.observed_peak:
        ratio = resource.provisioned / resource.observed_peak
        if ratio > thresholds.oversize_ratio:
            findings.append(
                _finding(resource, Rule.OVERSIZED, provisioned_to_peak=round(ratio, 2))
            )

    if resource.weekday_utilisation and resource.weekend_utilisation:
        ratio = resource.weekday_utilisation / resource.weekend_utilisation
        if ratio > thresholds.weekend_ratio:
            findings.append(
                _finding(resource, Rule.PEAK_SHAPED_ALWAYS_ON,
                         weekday_to_weekend=round(ratio, 2))
            )

    if not any(key in resource.tags for key in thresholds.owner_tag_keys):
        findings.append(_finding(resource, Rule.UNTAGGED, tags=dict(resource.tags)))

    return findings, gaps


def classify_with_gaps(
    inputs: Inputs, thresholds: Thresholds, as_of: datetime
) -> tuple[list[Finding], list[Gap]]:
    """Findings, and the checks that could not run for want of a field."""
    findings: list[Finding] = []
    gaps: list[Gap] = []
    for resource in inputs.matched:
        found, missed = _classify_one(resource, thresholds, as_of)
        findings += found
        gaps += missed
    return findings, gaps


def classify(inputs: Inputs, thresholds: Thresholds, as_of: datetime) -> list[Finding]:
    """Findings only. Kept so nothing that calls it today has to change."""
    return classify_with_gaps(inputs, thresholds, as_of)[0]
