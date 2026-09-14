"""Where every changed resource ends up.

The invariant is the point of this module: a total that quietly omits a resource
is the confident wrong answer this repository exists to catch, so the buckets are
made to sum to the number of changes before any pricing exists to get it wrong.
"""

from test_plan_parse import a_change, a_plan

from plan_cost.coverage import Bucket, summarise
from plan_cost.plan import parse_plan


def changes_of(*raw):
    return parse_plan(a_plan(list(raw))).changes


def everything_priced(key):
    return True


def nothing_priced(key):
    return False


def test_a_priced_type_with_a_row_is_priced():
    changes = changes_of(
        a_change(
            ["create"],
            type="google_compute_instance",
            after={"zone": "us-central1-a", "machine_type": "e2-small"},
        )
    )
    assert summarise(changes, has_row=everything_priced).buckets[0] is Bucket.PRICED


def test_a_priced_type_without_a_row_is_not_priced_at_zero():
    changes = changes_of(
        a_change(
            ["create"],
            type="google_compute_disk",
            after={"zone": "us-central1-a", "type": "pd-balanced", "size": 500},
        )
    )
    assert summarise(changes, has_row=nothing_priced).buckets[0] is Bucket.NO_PRICE_ROW


def test_an_unknown_attribute_beats_a_missing_row():
    """An attribute that is not known yet is why no row could match, so saying
    the row is missing would name the wrong problem."""
    changes = changes_of(
        a_change(
            ["create"],
            type="google_compute_instance",
            after={"zone": "us-central1-a"},
            after_unknown={"machine_type": True},
        )
    )
    assert summarise(changes, has_row=nothing_priced).buckets[0] is Bucket.UNKNOWN_UNTIL_APPLY


def test_a_resource_from_another_provider_is_not_priceable():
    changes = changes_of(
        a_change(["create"], type="incident_io_team", provider="incident-io/incident")
    )
    summary = summarise(changes, has_row=everything_priced)
    assert summary.buckets[0] is Bucket.NOT_PRICEABLE
    assert summary.reasons[0] == "not a cloud resource"


def test_no_op_and_read_are_counted_but_never_priced():
    changes = changes_of(a_change(["no-op"]), a_change(["read"]))
    assert summarise(changes, has_row=everything_priced).buckets == [
        Bucket.NO_CHANGE,
        Bucket.NO_CHANGE,
    ]


def test_every_change_lands_in_exactly_one_bucket():
    changes = changes_of(
        a_change(["create"], type="google_compute_instance",
                 after={"zone": "us-central1-a", "machine_type": "e2-small"}),
        a_change(["create"], type="google_compute_disk",
                 after={"zone": "us-central1-a", "type": "pd-ssd", "size": 20}),
        a_change(["create"], type="google_storage_bucket", after={"location": "US"}),
        a_change(["no-op"]),
        a_change(["create"], type="datadog_monitor", provider="DataDog/datadog"),
    )
    summary = summarise(changes, has_row=lambda key: "machine-type" in key)
    assert len(summary.buckets) == len(changes)
    assert sum(summary.counts.values()) == len(changes)


def test_the_counts_always_sum_to_the_number_of_changes():
    changes = changes_of(*[a_change(["create"], type="google_storage_bucket") for _ in range(7)])
    summary = summarise(changes, has_row=nothing_priced)
    assert sum(summary.counts.values()) == 7


# Every key the pricer looked for and did not find, so the report can name the
# command that would add them. The bucket reason keeps only the first, which is
# enough to explain one resource and not enough to instruct anyone.


def an_instance(address, machine_type):
    return a_change(
        ["create"],
        address=address,
        type="google_compute_instance",
        after={"zone": "europe-west1-b", "machine_type": machine_type},
    )


def test_a_missing_key_is_collected():
    summary = summarise(changes_of(an_instance("a", "e2-small")), has_row=nothing_priced)
    assert summary.missing_keys == ("google/machine-type/e2-small/europe-west1",)


def test_two_resources_missing_the_same_key_report_it_once():
    summary = summarise(
        changes_of(an_instance("a", "e2-small"), an_instance("b", "e2-small")),
        has_row=nothing_priced,
    )
    assert summary.missing_keys == ("google/machine-type/e2-small/europe-west1",)


def test_a_resource_missing_two_keys_reports_both():
    """A machine type change looks for the old row and the new one. The bucket
    reason keeps the first, so the second was being lost."""
    changes = changes_of(
        a_change(
            ["update"],
            type="google_compute_instance",
            before={"zone": "europe-west1-b", "machine_type": "e2-small"},
            after={"zone": "europe-west1-b", "machine_type": "n2-standard-8"},
        )
    )
    assert summarise(changes, has_row=nothing_priced).missing_keys == (
        "google/machine-type/e2-small/europe-west1",
        "google/machine-type/n2-standard-8/europe-west1",
    )


def test_they_come_back_sorted():
    """So the same plan prints the same list every run."""
    summary = summarise(
        changes_of(an_instance("a", "n2-standard-8"), an_instance("b", "e2-small")),
        has_row=nothing_priced,
    )
    assert list(summary.missing_keys) == sorted(summary.missing_keys)


def test_a_fully_priced_plan_reports_none():
    summary = summarise(changes_of(an_instance("a", "e2-small")), has_row=everything_priced)
    assert summary.missing_keys == ()


def test_a_plan_with_nothing_priceable_reports_none():
    """Absent and unpriceable are different. Nothing here was ever looked up,
    so no row is missing and there is nothing to refresh."""
    changes = changes_of(
        a_change(["create"], type="incident_io_team", provider="incident-io/incident")
    )
    assert summarise(changes, has_row=nothing_priced).missing_keys == ()


def test_an_unknown_attribute_contributes_no_missing_key():
    """Nothing was looked up, because nothing was known to look up."""
    changes = changes_of(
        a_change(
            ["create"],
            type="google_compute_instance",
            after={"zone": "europe-west1-b"},
            after_unknown={"machine_type": True},
        )
    )
    assert summarise(changes, has_row=nothing_priced).missing_keys == ()
