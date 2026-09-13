"""The deterministic rules.

The labels rule is the one that earns its place. A node pool carries two label
attributes and only one of them reaches a bill, so a rule written against the
obvious attribute would stay silent on unattributed spend and fire on
infrastructure that is labelled correctly.
"""

from test_plan_parse import a_change, a_plan

from plan_cost.plan import parse_plan
from plan_cost.rules import findings_for

SEVERITIES = {
    "node_pool_without_autoscaling": "block",
    "no_billing_labels": "review",
    "boot_disk_outlives_instance": "review",
}


def findings(*raw):
    return findings_for(parse_plan(a_plan(list(raw))).changes, SEVERITIES)


def node_pool(**after):
    attributes = {"location": "us-central1", "node_config": [{"machine_type": "e2-standard-4"}]}
    attributes.update(after)
    return a_change(
        ["create"],
        address="google_container_node_pool.primary",
        type="google_container_node_pool",
        after=attributes,
    )


def rules_fired(*raw):
    return [finding.rule for finding in findings(*raw)]


def test_a_node_pool_with_no_autoscaling_fires_at_its_configured_severity():
    fired = findings(node_pool(node_count=3, node_config=[{"machine_type": "e2-standard-4",
                                                          "resource_labels": {"team": "x"}}]))
    assert [(f.rule, f.severity) for f in fired] == [
        ("node_pool_without_autoscaling", "block")
    ]


def test_a_node_pool_with_autoscaling_does_not_fire():
    pool = node_pool(
        autoscaling=[{"min_node_count": 1, "max_node_count": 5}],
        node_config=[{"machine_type": "e2-standard-4", "resource_labels": {"team": "x"}}],
    )
    assert rules_fired(pool) == []


def test_an_attribute_not_known_until_apply_cannot_break_a_rule():
    """Firing on an unknown attribute would be a guess wearing a finding."""
    pool = a_change(
        ["create"],
        type="google_container_node_pool",
        after={"location": "us-central1",
               "node_config": [{"machine_type": "e2-standard-4",
                                "resource_labels": {"team": "x"}}]},
        after_unknown={"autoscaling": True},
    )
    assert rules_fired(pool) == []


def test_kubernetes_labels_are_not_billing_labels():
    """node_config.labels are Kubernetes labels. They never reach a bill, so a
    pool carrying only those is still unattributed spend."""
    pool = node_pool(
        node_count=3,
        node_config=[{"machine_type": "e2-standard-4", "labels": {"workload": "platform"}}],
    )
    assert "no_billing_labels" in rules_fired(pool)


def test_billing_labels_on_a_node_pool_satisfy_the_rule():
    pool = node_pool(
        node_count=3,
        node_config=[{"machine_type": "e2-standard-4", "resource_labels": {"team": "platform"}}],
    )
    assert "no_billing_labels" not in rules_fired(pool)


def test_an_instance_without_labels_is_unattributed_spend():
    instance = a_change(
        ["create"], type="google_compute_instance",
        after={"zone": "us-central1-a", "machine_type": "e2-small"},
    )
    assert "no_billing_labels" in rules_fired(instance)


def test_an_empty_label_map_is_no_better_than_none():
    instance = a_change(
        ["create"], type="google_compute_instance",
        after={"zone": "us-central1-a", "machine_type": "e2-small", "labels": {}},
    )
    assert "no_billing_labels" in rules_fired(instance)


def test_a_boot_disk_that_outlives_its_instance_fires():
    instance = a_change(
        ["create"], type="google_compute_instance",
        after={"zone": "us-central1-a", "machine_type": "e2-small",
               "labels": {"team": "x"}, "boot_disk": [{"auto_delete": False}]},
    )
    fired = findings(instance)
    assert [f.rule for f in fired] == ["boot_disk_outlives_instance"]
    assert fired[0].attribute == "boot_disk.auto_delete"


def test_the_default_boot_disk_does_not_fire():
    """auto_delete defaults to true, so the rule fires only on an explicit false."""
    instance = a_change(
        ["create"], type="google_compute_instance",
        after={"zone": "us-central1-a", "machine_type": "e2-small",
               "labels": {"team": "x"}, "boot_disk": [{"auto_delete": True}]},
    )
    assert rules_fired(instance) == []


def test_nothing_fires_on_a_resource_being_deleted():
    """A finding on a resource that is going away is advice nobody can take."""
    instance = a_change(
        ["delete"], type="google_compute_instance",
        before={"zone": "us-central1-a", "machine_type": "e2-small"},
    )
    assert rules_fired(instance) == []


def test_a_sensitive_value_is_named_but_never_printed():
    instance = a_change(
        ["create"], type="google_compute_instance",
        after={"zone": "us-central1-a", "machine_type": "e2-small", "labels": {}},
        after_sensitive={"labels": True},
    )
    finding = findings(instance)[0]
    assert finding.attribute == "labels"
    assert finding.value is None


def test_a_rule_missing_from_the_policy_is_not_invented():
    instance = a_change(
        ["create"], type="google_compute_instance",
        after={"zone": "us-central1-a", "machine_type": "e2-small"},
    )
    assert findings_for(parse_plan(a_plan([instance])).changes, {}) == []
