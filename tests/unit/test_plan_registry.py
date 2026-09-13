"""What the tool knows how to price, and what it admits it cannot.

The labels test is here because the obvious attribute is the wrong one. A node
pool's node_config.labels are Kubernetes labels that never reach a bill; the
ones that do are node_config.resource_labels. A rule written against the first
would fire on correctly labelled infrastructure and stay silent on unattributed
spend.
"""

import pytest

from plan_cost.registry import (
    UnknownAttribute,
    billing_label_attribute,
    is_priced,
    not_priceable_reason,
    units_for,
)


def test_a_node_pool_is_priced_on_its_machine_type_and_node_count():
    units = units_for(
        "google_container_node_pool",
        {
            "location": "us-central1",
            "node_count": 3,
            "node_config": [{"machine_type": "e2-standard-4"}],
        },
    )
    assert [(u.key, u.quantity) for u in units] == [
        ("google/machine-type/e2-standard-4/us-central1", 3)
    ]


def test_a_node_pool_with_autoscaling_is_priced_at_its_floor():
    """Autoscaled capacity is a range, and the floor is the part the plan
    guarantees. The report says so rather than presenting it as the cost."""
    units = units_for(
        "google_container_node_pool",
        {
            "location": "us-central1",
            "autoscaling": [{"min_node_count": 2, "max_node_count": 10}],
            "node_config": [{"machine_type": "e2-standard-4"}],
        },
    )
    assert units[0].quantity == 2
    assert units[0].at_minimum is True


def test_a_zone_is_reduced_to_its_region_because_prices_are_regional():
    units = units_for(
        "google_compute_instance",
        {"zone": "us-central1-a", "machine_type": "e2-small"},
    )
    assert units[0].key == "google/machine-type/e2-small/us-central1"


def test_an_attribute_not_known_until_apply_is_not_a_price_of_zero():
    with pytest.raises(UnknownAttribute):
        units_for("google_compute_instance", {"zone": "us-central1-a"})


def test_a_disk_is_priced_by_size_even_though_no_row_ships_for_one():
    units = units_for(
        "google_compute_disk",
        {"zone": "us-central1-a", "type": "pd-balanced", "size": 500},
    )
    assert [(u.key, u.quantity) for u in units] == [
        ("google/disk/pd-balanced/us-central1", 500)
    ]


def test_billing_labels_on_a_node_pool_are_not_the_kubernetes_ones():
    assert billing_label_attribute("google_container_node_pool") == "node_config.resource_labels"


def test_billing_labels_elsewhere_are_the_obvious_attribute():
    assert billing_label_attribute("google_compute_instance") == "labels"
    assert billing_label_attribute("google_compute_disk") == "labels"


def test_priced_types_are_known_and_others_are_not():
    assert is_priced("google_container_node_pool") is True
    assert is_priced("google_storage_bucket") is False


@pytest.mark.parametrize(
    "resource_type,provider,expected",
    [
        ("google_storage_bucket", "hashicorp/google", "usage-driven"),
        ("google_bigquery_dataset", "hashicorp/google", "usage-driven"),
        ("google_project_iam_member", "hashicorp/google", "no recurring cost"),
        ("incident_io_team", "incident-io/incident", "not a cloud resource"),
        ("datadog_monitor", "DataDog/datadog", "not a cloud resource"),
        ("google_pubsub_lite_topic", "hashicorp/google", "not modelled by this tool"),
    ],
)
def test_everything_unpriced_says_why(resource_type, provider, expected):
    assert not_priceable_reason(resource_type, provider) == expected
