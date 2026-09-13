"""Where every changed resource ends up.

One bucket each, and the buckets sum to the number of changes. That invariant
is checked here rather than only in a test, because a total that quietly omits
a resource is exactly the confident wrong answer this repository exists to
catch, and the check costs nothing.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .plan import Action, ResourceChange
from .registry import Unit, UnknownAttribute, is_priced, not_priceable_reason, units_for


class Bucket(Enum):
    PRICED = "priced"
    UNKNOWN_UNTIL_APPLY = "unknown until apply"
    NO_PRICE_ROW = "no price row"
    NOT_PRICEABLE = "not priceable"
    NO_CHANGE = "no change"


@dataclass(frozen=True)
class Summary:
    buckets: list[Bucket]
    reasons: list[str]
    before: list[tuple[Unit, ...]]
    after: list[tuple[Unit, ...]]
    counts: dict[Bucket, int]


def summarise(
    changes: Sequence[ResourceChange], *, has_row: Callable[[str], bool]
) -> Summary:
    buckets: list[Bucket] = []
    reasons: list[str] = []
    before: list[tuple[Unit, ...]] = []
    after: list[tuple[Unit, ...]] = []

    for change in changes:
        bucket, reason, prior, planned = _classify(change, has_row)
        buckets.append(bucket)
        reasons.append(reason)
        before.append(prior)
        after.append(planned)

    counts = dict(Counter(buckets))
    if sum(counts.values()) != len(changes):
        raise RuntimeError(
            "coverage lost a resource: "
            f"{sum(counts.values())} counted against {len(changes)} changed"
        )
    return Summary(buckets=buckets, reasons=reasons, before=before, after=after, counts=counts)


def _classify(
    change: ResourceChange, has_row: Callable[[str], bool]
) -> tuple[Bucket, str, tuple[Unit, ...], tuple[Unit, ...]]:
    if change.action in (Action.NO_CHANGE, Action.READ):
        return Bucket.NO_CHANGE, "", (), ()

    if not is_priced(change.type):
        return Bucket.NOT_PRICEABLE, not_priceable_reason(change.type, change.provider), (), ()

    prior: tuple[Unit, ...] = ()
    planned: tuple[Unit, ...] = ()
    unknown = ""

    if change.action in (Action.DELETE, Action.UPDATE, Action.REPLACE):
        try:
            prior = units_for(change.type, change.before)
        except UnknownAttribute as exc:
            unknown = str(exc)
    if change.action in (Action.CREATE, Action.UPDATE, Action.REPLACE):
        try:
            planned = units_for(change.type, change.after)
        except UnknownAttribute as exc:
            unknown = str(exc)

    if unknown:
        # An attribute nobody knows yet is why no row could match, so saying the
        # row is missing would name the wrong problem.
        return Bucket.UNKNOWN_UNTIL_APPLY, unknown, prior, planned

    missing = [unit.key for unit in prior + planned if not has_row(unit.key)]
    if missing:
        return Bucket.NO_PRICE_ROW, missing[0], prior, planned
    return Bucket.PRICED, "", prior, planned


def is_sensitive(sensitive: Mapping[str, Any], path: str) -> bool:
    """Whether the plan marks this dotted attribute path as sensitive.

    Findings quote attributes and findings go to build logs, so a value the
    plan flagged is named but never printed.
    """
    node: Any = sensitive
    for part in path.split("."):
        if isinstance(node, list):
            node = node[0] if node else None
        if not isinstance(node, Mapping) or part not in node:
            return False
        node = node[part]
    if isinstance(node, list):
        node = node[0] if node else False
    return node is True
