"""RCAs arrive structured. Parsing arbitrary postmortem prose would put a
probabilistic step underneath every deterministic check above it.
"""

import json
from datetime import datetime

from rca_agent.types import Category, load_corpus, load_rca

DOCUMENT = {
    "rca_id": "rca-example",
    "severity": "sev2",
    "timeline": [
        {"name": "detection", "at": "2026-03-01T09:12:00"},
        {"name": "escalation", "at": "2026-03-01T09:20:00"},
        {"name": "mitigation", "at": "2026-03-01T09:48:00"},
        {"name": "resolution", "at": "2026-03-01T10:30:00"},
    ],
    "impact": "412 merchants saw checkout errors for 78 minutes.",
    "stated_cause": "A schema migration held a lock the write path depended on.",
    "contributing_factors": [
        "The migration had no lock timeout.",
        "The rollback ran against the wrong replica, extending the outage.",
    ],
    "narrative": "Rae Lindqvist rolled the deploy back at 09:48.",
    "participants": ["Rae Lindqvist", "Sam Okafor"],
    "action_items": [
        {
            "title": "Add a lock timeout to migrations",
            "owner": "Rae Lindqvist",
            "due": "2026-04-01T00:00:00",
            "tracker_ref": "PLAT-2211",
            "category": "PREVENT",
            "state": "closed",
            "created": "2026-03-02T00:00:00",
            "closure_evidence": "PR 4412",
        }
    ],
    "closed_at": "2026-03-03T00:00:00",
    "followups_exported_at": "2026-03-04T00:00:00",
}


def test_an_rca_loads_with_its_timeline_parsed(tmp_path):
    path = tmp_path / "rca-example.json"
    path.write_text(json.dumps(DOCUMENT))

    rca = load_rca(path)

    assert rca.rca_id == "rca-example"
    assert rca.moment("detection") == datetime(2026, 3, 1, 9, 12)
    assert rca.moment("nonexistent") is None


def test_action_items_carry_their_category_and_state(tmp_path):
    path = tmp_path / "rca-example.json"
    path.write_text(json.dumps(DOCUMENT))

    item = load_rca(path).action_items[0]

    assert item.category is Category.PREVENT
    assert item.state == "closed"
    assert item.closure_evidence == "PR 4412"


def test_a_missing_optional_field_loads_as_absent_rather_than_failing(tmp_path):
    """An action item with no owner is a defect to report, not a parse error that
    stops the whole review."""
    document = json.loads(json.dumps(DOCUMENT))
    document["action_items"][0].pop("owner")
    document["action_items"][0].pop("category")

    path = tmp_path / "rca-example.json"
    path.write_text(json.dumps(document))

    item = load_rca(path).action_items[0]

    assert item.owner is None
    assert item.category is None


def test_an_open_rca_has_no_closure_date(tmp_path):
    document = json.loads(json.dumps(DOCUMENT))
    document["closed_at"] = None

    path = tmp_path / "rca-open.json"
    path.write_text(json.dumps(document))

    assert load_rca(path).closed_at is None


def test_a_corpus_loads_every_document_in_a_directory(tmp_path):
    for index in range(3):
        document = json.loads(json.dumps(DOCUMENT))
        document["rca_id"] = f"rca-{index}"
        (tmp_path / f"rca-{index}.json").write_text(json.dumps(document))

    corpus = load_corpus(tmp_path)

    assert {rca.rca_id for rca in corpus} == {"rca-0", "rca-1", "rca-2"}
