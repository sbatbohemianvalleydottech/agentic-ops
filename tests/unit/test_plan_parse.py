"""Reading a plan.

Two of these would silently corrupt a total if they were wrong: a replacement
written in either order, and a format version nobody checked. Both were wrong in
the first draft of the design, which is why they are the first tests here.
"""

import json

import pytest

from plan_cost.plan import Action, PlanError, load_plan, parse_plan


def a_change(actions, **kw):
    return {
        "address": kw.get("address", "google_compute_instance.web"),
        "type": kw.get("type", "google_compute_instance"),
        "provider_name": kw.get("provider", "registry.terraform.io/hashicorp/google"),
        "change": {
            "actions": actions,
            "before": kw.get("before"),
            "after": kw.get("after"),
            "after_unknown": kw.get("after_unknown", {}),
            "after_sensitive": kw.get("after_sensitive", {}),
        },
    }


def a_plan(changes, *, format_version="1.2", variables=None):
    doc = {"format_version": format_version, "resource_changes": changes}
    if variables is not None:
        doc["variables"] = variables
    return doc


@pytest.mark.parametrize(
    "actions,expected",
    [
        (["create"], Action.CREATE),
        (["read"], Action.READ),
        (["update"], Action.UPDATE),
        (["delete"], Action.DELETE),
        (["no-op"], Action.NO_CHANGE),
        (["delete", "create"], Action.REPLACE),
        (["create", "delete"], Action.REPLACE),
    ],
)
def test_every_action_combination_the_format_defines(actions, expected):
    plan = parse_plan(a_plan([a_change(actions)]))
    assert plan.changes[0].action is expected


def test_both_replacement_orders_mean_the_same_thing():
    """A create-before-destroy replacement is written ["create","delete"].

    Priced as a new resource rather than a difference, it would overstate the
    cost of exactly the changes careful teams write.
    """
    destroy_first = parse_plan(a_plan([a_change(["delete", "create"])])).changes[0]
    create_first = parse_plan(a_plan([a_change(["create", "delete"])])).changes[0]
    assert destroy_first.action is create_first.action is Action.REPLACE


def test_an_unsupported_format_version_is_refused_by_name():
    with pytest.raises(PlanError) as raised:
        parse_plan(a_plan([], format_version="2.0"))
    assert "2.0" in str(raised.value)


def test_any_minor_version_of_a_supported_major_is_accepted():
    assert parse_plan(a_plan([], format_version="1.9")).format_version == "1.9"


def test_a_missing_format_version_is_refused():
    with pytest.raises(PlanError):
        parse_plan({"resource_changes": []})


def test_the_environment_comes_from_the_plans_own_variables():
    doc = a_plan([], variables={"environment": {"value": "staging"}})
    assert parse_plan(doc).environment == "staging"


def test_a_plan_without_that_variable_has_no_environment():
    assert parse_plan(a_plan([])).environment is None


def test_a_plan_with_no_changes_at_all_parses():
    assert parse_plan({"format_version": "1.2"}).changes == ()


def test_a_delete_keeps_its_prior_attributes_and_plans_none():
    change = parse_plan(
        a_plan([a_change(["delete"], before={"machine_type": "e2-small"}, after=None)])
    ).changes[0]
    assert change.before["machine_type"] == "e2-small"
    assert change.after == {}


def test_attributes_not_known_until_apply_survive_parsing():
    change = parse_plan(
        a_plan([a_change(["create"], after={}, after_unknown={"machine_type": True})])
    ).changes[0]
    assert change.after_unknown == {"machine_type": True}


def test_sensitive_paths_survive_parsing():
    """A finding quotes attributes and findings go to build logs, so the tool
    has to know which values it must never print."""
    change = parse_plan(
        a_plan([a_change(["create"], after_sensitive={"metadata": {"password": True}})])
    ).changes[0]
    assert change.after_sensitive == {"metadata": {"password": True}}


def test_the_provider_is_kept_so_non_cloud_resources_can_be_told_apart():
    change = parse_plan(
        a_plan([a_change(["create"], provider="registry.terraform.io/incident-io/incident")])
    ).changes[0]
    assert "incident" in change.provider


def test_a_plan_is_loaded_from_a_file(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(a_plan([a_change(["create"])])), encoding="utf-8")
    assert load_plan(path).changes[0].action is Action.CREATE


def test_a_file_that_is_not_json_is_refused_as_a_plan(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(PlanError):
        load_plan(path)
