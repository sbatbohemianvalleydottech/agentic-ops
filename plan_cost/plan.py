"""Read a Terraform plan in its documented JSON form.

The two traps here are both silent. A replacement can be written in either
order, and treating ["create","delete"] as a plain create prices a swap as a
whole new resource with no credit for the old one. A format version nobody
checked can move the fields underneath every total the tool prints, so an
unrecognised version is refused rather than parsed hopefully.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

SUPPORTED_MAJOR = "1"


class PlanError(Exception):
    """The plan cannot be read. Distinct from the plan being expensive."""


class Action(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    REPLACE = "replace"
    NO_CHANGE = "no change"


# The complete set the format defines. Both replacement orders collapse to one
# action, which is the whole reason this table is explicit rather than inferred.
ACTIONS: dict[tuple[str, ...], Action] = {
    ("no-op",): Action.NO_CHANGE,
    ("create",): Action.CREATE,
    ("read",): Action.READ,
    ("update",): Action.UPDATE,
    ("delete",): Action.DELETE,
    ("delete", "create"): Action.REPLACE,
    ("create", "delete"): Action.REPLACE,
}


@dataclass(frozen=True)
class ResourceChange:
    address: str
    type: str
    provider: str
    action: Action
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    after_unknown: Mapping[str, Any]
    after_sensitive: Mapping[str, Any]


@dataclass(frozen=True)
class Plan:
    format_version: str
    environment: str | None
    changes: tuple[ResourceChange, ...]


def parse_plan(document: Mapping[str, Any]) -> Plan:
    version = document.get("format_version")
    if not isinstance(version, str) or not version:
        raise PlanError(
            "no format_version in this document, so it is not the JSON form of a plan"
        )
    if version.split(".")[0] != SUPPORTED_MAJOR:
        raise PlanError(
            f"plan format version {version} has not been checked against this tool, "
            f"which reads {SUPPORTED_MAJOR}.x"
        )
    raw_changes = document.get("resource_changes") or []
    return Plan(
        format_version=version,
        environment=_environment(document),
        changes=tuple(_resource_change(raw) for raw in raw_changes),
    )


def load_plan(path: Path) -> Plan:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"{path} could not be read as JSON: {exc}") from exc
    if not isinstance(document, Mapping):
        raise PlanError(f"{path} holds JSON, but not an object, so it is not a plan")
    return parse_plan(document)


def _environment(document: Mapping[str, Any]) -> str | None:
    """The environment the plan is for, when the pipeline passed one."""
    variables = document.get("variables") or {}
    entry = variables.get("environment") or {}
    value = entry.get("value") if isinstance(entry, Mapping) else None
    return value if isinstance(value, str) and value else None


def _resource_change(raw: Mapping[str, Any]) -> ResourceChange:
    change = raw.get("change") or {}
    actions = tuple(change.get("actions") or ())
    action = ACTIONS.get(actions)
    if action is None:
        raise PlanError(
            f"{raw.get('address', 'a resource')} carries actions {list(actions)}, "
            "which this tool does not recognise"
        )
    return ResourceChange(
        address=str(raw.get("address", "")),
        type=str(raw.get("type", "")),
        provider=str(raw.get("provider_name", "")),
        action=action,
        before=change.get("before") or {},
        after=change.get("after") or {},
        after_unknown=change.get("after_unknown") or {},
        after_sensitive=change.get("after_sensitive") or {},
    )
