"""Deterministic checks over the planned attributes.

Three rules, each about a cost consequence that is visible in the document
before anything is built. No model is consulted, because none of this is a
judgement: an absent autoscaling block is a fact.

Two restraints matter as much as the rules. Nothing fires on an attribute the
plan does not yet know, because that would be a guess wearing a finding. And
nothing fires on a resource being deleted, because a finding about something
going away is advice nobody can take.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .coverage import is_sensitive
from .plan import Action, ResourceChange
from .registry import billing_label_attribute

CHANGEABLE = (Action.CREATE, Action.UPDATE, Action.REPLACE)

NODE_POOL = "google_container_node_pool"
INSTANCE = "google_compute_instance"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    address: str
    attribute: str
    value: str | None
    why: str


def findings_for(
    changes: Sequence[ResourceChange], severities: Mapping[str, str]
) -> list[Finding]:
    found: list[Finding] = []
    for change in changes:
        if change.action not in CHANGEABLE:
            continue
        for rule in (_without_autoscaling, _without_billing_labels, _disk_outlives_instance):
            finding = rule(change, severities)
            if finding is not None:
                found.append(finding)
    return found


def _without_autoscaling(
    change: ResourceChange, severities: Mapping[str, str]
) -> Finding | None:
    name = "node_pool_without_autoscaling"
    severity = severities.get(name)
    if severity is None or change.type != NODE_POOL:
        return None
    if _unknown_at(change.after_unknown, "autoscaling"):
        return None
    if _at(change.after, "autoscaling"):
        return None
    node_count = change.after.get("node_count")
    value = "absent" if node_count is None else f"absent, node_count = {node_count}"
    return Finding(
        rule=name,
        severity=severity,
        address=change.address,
        attribute="autoscaling",
        value=None if is_sensitive(change.after_sensitive, "autoscaling") else value,
        why="capacity that can never be reclaimed, which is the driver cost_agent "
        "finds on bills sixty days later",
    )


def _without_billing_labels(
    change: ResourceChange, severities: Mapping[str, str]
) -> Finding | None:
    name = "no_billing_labels"
    severity = severities.get(name)
    attribute = billing_label_attribute(change.type)
    if severity is None or not attribute:
        return None
    if _unknown_at(change.after_unknown, attribute):
        return None
    labels = _at(change.after, attribute)
    if labels:
        return None
    value = "empty" if isinstance(labels, Mapping) else "absent"
    return Finding(
        rule=name,
        severity=severity,
        address=change.address,
        attribute=attribute,
        value=None if is_sensitive(change.after_sensitive, attribute) else value,
        why="spend that cannot be attributed to a team, which is where "
        "accountability disappears",
    )


def _disk_outlives_instance(
    change: ResourceChange, severities: Mapping[str, str]
) -> Finding | None:
    name = "boot_disk_outlives_instance"
    severity = severities.get(name)
    if severity is None or change.type != INSTANCE:
        return None
    attribute = "boot_disk.auto_delete"
    if _unknown_at(change.after_unknown, attribute):
        return None
    if _at(change.after, attribute) is not False:
        # auto_delete defaults to true, so only an explicit false is a finding.
        return None
    return Finding(
        rule=name,
        severity=severity,
        address=change.address,
        attribute=attribute,
        value=None if is_sensitive(change.after_sensitive, attribute) else "false",
        why="the disk keeps billing after the instance is gone, which is the "
        "orphaned-storage case nobody goes looking for",
    )


def _at(attributes: Mapping[str, Any], path: str) -> Any:
    """Read a dotted attribute path, stepping into the lists that blocks become."""
    node: Any = attributes
    for part in path.split("."):
        if isinstance(node, list):
            node = node[0] if node else None
        if not isinstance(node, Mapping):
            return None
        node = node.get(part)
    if isinstance(node, list):
        return node[0] if node else None
    return node


def _unknown_at(unknown: Mapping[str, Any], path: str) -> bool:
    """Whether the plan says this path, or anything containing it, is unknown."""
    node: Any = unknown
    for part in path.split("."):
        if node is True:
            return True
        if isinstance(node, list):
            node = node[0] if node else None
        if not isinstance(node, Mapping):
            return False
        node = node.get(part)
    if isinstance(node, list):
        node = node[0] if node else False
    return node is True
