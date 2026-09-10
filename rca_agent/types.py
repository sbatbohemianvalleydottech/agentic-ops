"""Structured incident reviews.

Optional fields load as absent rather than raising. An action item with no owner
is a defect to report, not a parse error that stops the whole review before it
gets to the findings.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class Category(Enum):
    """The four action item categories from PagerDuty's postmortem template.

    PREVENT is the one that matters. An RCA with none of them has accepted the
    recurrence, however good the rest of the document is.
    """

    PREVENT = "prevent"
    PREPARE = "prepare"
    PROCESS = "process"
    COMMS = "comms"


class Dimension(Enum):
    TIMELINE_COMPLETENESS = "timeline_completeness"
    IMPACT_QUANTIFIED = "impact_quantified"
    BLAMELESS = "blameless"
    ACTION_ITEM_COMPLETE = "action_item_complete"
    HAS_PREVENTIVE_ACTION = "has_preventive_action"
    CONTRIBUTING_FACTORS_PRESENT = "contributing_factors_present"
    CAUSE_NOT_TRIGGER = "cause_not_trigger"
    NO_ALTERNATE_REALITY = "no_alternate_reality"
    ACTIONS_WOULD_PREVENT = "actions_would_prevent"


JUDGEMENT_DIMENSIONS = (
    Dimension.CAUSE_NOT_TRIGGER,
    Dimension.NO_ALTERNATE_REALITY,
    Dimension.ACTIONS_WOULD_PREVENT,
)


@dataclass(frozen=True)
class TimelineMoment:
    name: str
    at: datetime


@dataclass(frozen=True)
class ActionItem:
    title: str
    state: str
    created: datetime
    owner: str | None = None
    due: datetime | None = None
    tracker_ref: str | None = None
    category: Category | None = None
    closure_evidence: str | None = None


@dataclass(frozen=True)
class Defect:
    dimension: Dimension
    detail: str
    quote: str
    severity: str = "major"

    def __post_init__(self):
        if not self.quote.strip():
            raise ValueError(
                f"{self.dimension.value} defect has no quote; a finding nobody can "
                "check against the document is not reported"
            )


@dataclass(frozen=True)
class RCA:
    rca_id: str
    severity: str
    timeline: tuple[TimelineMoment, ...]
    impact: str
    stated_cause: str
    contributing_factors: tuple[str, ...]
    narrative: str
    participants: tuple[str, ...]
    action_items: tuple[ActionItem, ...]
    closed_at: datetime | None = None
    followups_exported_at: datetime | None = None

    def moment(self, name: str) -> datetime | None:
        return next((m.at for m in self.timeline if m.name == name), None)

    @property
    def cause_fields(self) -> tuple[str, ...]:
        """Where blame is looked for. Never the narrative: a person belongs there,
        and flagging it would train users to ignore the check."""
        return (self.stated_cause, *self.contributing_factors)


def _when(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


def _category(raw: str | None) -> Category | None:
    if not raw:
        return None
    try:
        return Category(raw.lower())
    except ValueError:
        # An unrecognised category is treated as absent, which surfaces as the
        # same defect. Raising here would stop the review over a typo.
        return None


def load_rca(path: Path) -> RCA:
    raw = json.loads(Path(path).read_text())

    return RCA(
        rca_id=raw["rca_id"],
        severity=raw.get("severity", ""),
        timeline=tuple(
            TimelineMoment(name=m["name"], at=datetime.fromisoformat(m["at"]))
            for m in raw.get("timeline", [])
        ),
        impact=raw.get("impact", ""),
        stated_cause=raw.get("stated_cause", ""),
        contributing_factors=tuple(raw.get("contributing_factors", [])),
        narrative=raw.get("narrative", ""),
        participants=tuple(raw.get("participants", [])),
        action_items=tuple(
            ActionItem(
                title=item["title"],
                state=item.get("state", "open"),
                created=datetime.fromisoformat(item["created"]),
                owner=item.get("owner"),
                due=_when(item.get("due")),
                tracker_ref=item.get("tracker_ref"),
                category=_category(item.get("category")),
                closure_evidence=item.get("closure_evidence"),
            )
            for item in raw.get("action_items", [])
        ),
        closed_at=_when(raw.get("closed_at")),
        followups_exported_at=_when(raw.get("followups_exported_at")),
    )


def load_corpus(directory: Path) -> list[RCA]:
    return [load_rca(path) for path in sorted(Path(directory).glob("*.json"))]
