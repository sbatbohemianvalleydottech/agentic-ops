"""What this tool knows how to price, and why it cannot price the rest.

This module is the seam. A second cloud is added here and in the price table,
and nowhere else, which is what keeps "extensible" from being a claim nobody
can check.

A plan fixes some costs completely and others not at all. A node pool's cost
follows from its machine type and node count. A bucket's cost is the volume
stored and the requests served, neither of which a plan knows. Saying so is
the point: a bucket priced at zero and added to a total is a lie of omission.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

ZONE = re.compile(r"^(?P<region>[a-z]+-[a-z]+\d+)-[a-z]$")


class UnknownAttribute(Exception):
    """A pricing attribute is not known until apply, so nothing can be priced."""


@dataclass(frozen=True)
class Unit:
    """One priced quantity: how many of a price row's unit this resource buys."""

    key: str
    quantity: Decimal
    at_minimum: bool = False


# Types whose recurring cost a plan determines, with the attribute carrying the
# labels that reach a bill. On a node pool that is deliberately not the obvious
# one: node_config.labels are Kubernetes labels and never appear on a bill.
BILLING_LABELS = {
    "google_container_node_pool": "node_config.resource_labels",
    "google_compute_instance": "labels",
    "google_compute_disk": "labels",
}

USAGE_DRIVEN = {
    "google_storage_bucket",
    "google_bigquery_dataset",
    "google_bigquery_table",
    "google_cloud_run_service",
    "google_cloudfunctions_function",
}

NO_RECURRING_COST = {
    "google_project_iam_member",
    "google_project_iam_binding",
    "google_project_iam_custom_role",
    "google_project_service",
    "google_service_account",
    "google_service_account_iam_member",
}


def is_priced(resource_type: str) -> bool:
    return resource_type in BILLING_LABELS


def billing_label_attribute(resource_type: str) -> str:
    """The attribute whose labels reach the billing export, per resource type."""
    return BILLING_LABELS.get(resource_type, "")


def not_priceable_reason(resource_type: str, provider: str) -> str:
    """Why a resource carries no price here. Every unpriced resource gets one."""
    if provider.rsplit("/", 1)[-1] != "google":
        return "not a cloud resource"
    if resource_type in USAGE_DRIVEN:
        return "usage-driven"
    if resource_type in NO_RECURRING_COST:
        return "no recurring cost"
    return "not modelled by this tool"


def units_for(resource_type: str, attributes: Mapping[str, Any]) -> tuple[Unit, ...]:
    """The priced quantities of one resource in one state.

    Raises UnknownAttribute when the plan does not yet know what it will build.
    That is a different answer from zero, and the coverage report keeps them apart.
    """
    if resource_type == "google_container_node_pool":
        return _node_pool(attributes)
    if resource_type == "google_compute_instance":
        return _instance(attributes)
    if resource_type == "google_compute_disk":
        return _disk(attributes)
    raise UnknownAttribute(f"{resource_type} is not priced by this tool")


def _node_pool(attributes: Mapping[str, Any]) -> tuple[Unit, ...]:
    region = _region(attributes)
    machine_type = _first_block(attributes, "node_config").get("machine_type")
    if not machine_type:
        raise UnknownAttribute("machine type is not known until apply")

    key = f"google/machine-type/{machine_type}/{region}"
    node_count = attributes.get("node_count")
    if isinstance(node_count, int):
        return (Unit(key=key, quantity=Decimal(node_count)),)

    autoscaling = _first_block(attributes, "autoscaling")
    floor = autoscaling.get("min_node_count", autoscaling.get("total_min_node_count"))
    if isinstance(floor, int):
        # Autoscaled capacity is a range. The floor is the part the plan
        # guarantees, and the report says it is a floor rather than the cost.
        return (Unit(key=key, quantity=Decimal(floor), at_minimum=True),)
    raise UnknownAttribute("neither a node count nor an autoscaling floor is known")


def _instance(attributes: Mapping[str, Any]) -> tuple[Unit, ...]:
    region = _region(attributes)
    machine_type = attributes.get("machine_type")
    if not machine_type:
        raise UnknownAttribute("machine type is not known until apply")
    return (Unit(key=f"google/machine-type/{machine_type}/{region}", quantity=Decimal(1)),)


def _disk(attributes: Mapping[str, Any]) -> tuple[Unit, ...]:
    region = _region(attributes)
    disk_type = attributes.get("type")
    size = attributes.get("size")
    if not disk_type or not isinstance(size, int):
        raise UnknownAttribute("disk type or size is not known until apply")
    return (Unit(key=f"google/disk/{disk_type}/{region}", quantity=Decimal(size)),)


def _first_block(attributes: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Blocks arrive as lists in a plan, even when only one is allowed."""
    block = attributes.get(name)
    if isinstance(block, list):
        return block[0] if block and isinstance(block[0], Mapping) else {}
    return block if isinstance(block, Mapping) else {}


def _region(attributes: Mapping[str, Any]) -> str:
    """Prices are regional, so a zone is reduced to its region and a resource
    with neither is left unpriced rather than priced somewhere else."""
    for field in ("region", "location", "zone"):
        value = attributes.get(field)
        if isinstance(value, str) and value:
            match = ZONE.match(value)
            return match.group("region") if match else value
    raise UnknownAttribute("no region or zone, so no regional price can apply")
