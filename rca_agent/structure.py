"""Deterministic checks over an incident review.

Pure. Given the document, the rubric and an analysis date, always the same
defects. `as_of` is a parameter rather than a clock read so a reviewer can
reproduce a run exactly.

Every defect quotes the text that produced it, enforced by the `Defect` type
itself. A finding nobody can check against the document is worse than no finding,
because someone then has to disprove it.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from .rubric import Rubric
from .types import RCA, Category, Defect, Dimension

HAS_QUANTITY = re.compile(r"\d")


@dataclass(frozen=True)
class Review:
    rca_id: str
    defects: tuple[Defect, ...] = ()
    requires_human_judgement: bool = False


def _timeline_defects(rca: RCA, rubric: Rubric) -> list[Defect]:
    defects = []
    present = {moment.name: moment.at for moment in rca.timeline}

    missing = [name for name in rubric.required_moments if name not in present]
    if missing:
        defects.append(
            Defect(
                dimension=Dimension.TIMELINE_COMPLETENESS,
                detail=f"missing required moment(s): {', '.join(missing)}",
                quote=(
                    "timeline records: "
                    + (", ".join(present) if present else "nothing")
                ),
            )
        )

    # Order matters as much as presence. Mitigation before detection means either
    # the timeline was reconstructed from memory, or detection happened
    # informally and was never recorded. Both are findings.
    ordered = [
        (name, present[name]) for name in rubric.required_moments if name in present
    ]
    for (earlier, at_earlier), (later, at_later) in zip(
        ordered, ordered[1:], strict=False
    ):
        if at_later < at_earlier:
            defects.append(
                Defect(
                    dimension=Dimension.TIMELINE_COMPLETENESS,
                    detail=f"{later} is timestamped before {earlier}",
                    quote=f"{earlier} at {at_earlier:%H:%M}, {later} at {at_later:%H:%M}",
                )
            )

    return defects


def _sentences(text: str) -> list[str]:
    """Crude on purpose. A full sentence splitter would be a dependency and a
    second thing to be wrong about; the question here is only whether a person
    and a phrase are near each other."""
    return [part for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _blame_phrase(field: str, lowered: str, rca: RCA, rubric: Rubric) -> str | None:
    """The phrase that blames somebody, or None.

    Two kinds. "Human error" names a person by construction and fires alone.
    "Failed to" does not: subsystems fail to do things constantly, and a check
    that reads "the job failed to start" as blame is the check nobody trusts by
    the second week. Those only fire when a person is the subject of the same
    sentence, which is somebody on the participant roster or one of the generic
    subjects the rubric lists.

    Found by running this against published incident reports, where the first
    real document produced a false positive.
    """
    for phrase in rubric.blame_phrases_standalone:
        if phrase in lowered:
            return phrase

    people = [name.lower() for name in rca.participants if name]
    for sentence in _sentences(lowered):
        # Whole words. "he" as a substring lives inside "the", which made
        # every sentence look like it had a person in it.
        has_person = any(name in sentence for name in people) or any(
            re.search(rf"\b{re.escape(subject)}\b", sentence)
            for subject in rubric.human_subjects
        )
        if not has_person:
            continue
        for phrase in rubric.blame_phrases:
            if phrase in sentence:
                return phrase
    return None


def _blameless_defects(rca: RCA, rubric: Rubric) -> list[Defect]:
    """Looks at the cause fields only. Never the narrative.

    "Sam restarted the service" is good practice and belongs in the narrative.
    "Sam failed to check the config" is the failure, and it belongs nowhere. A
    check that flagged the first would train people to ignore the second.
    """
    defects = []

    for field in rca.cause_fields:
        lowered = field.lower()

        phrase = _blame_phrase(field, lowered, rca, rubric)
        if phrase:
            defects.append(
                Defect(
                    dimension=Dimension.BLAMELESS,
                    detail=f"cause attributes the failure to a person: {phrase!r}",
                    quote=field,
                )
            )

        for name in rca.participants:
            if name and name in field:
                defects.append(
                    Defect(
                        dimension=Dimension.BLAMELESS,
                        detail=f"a named individual appears in a cause field: {name}",
                        quote=field,
                    )
                )
                break

    return defects


def _action_item_defects(rca: RCA) -> list[Defect]:
    defects = []

    for item in rca.action_items:
        # One defect per missing attribute, not one lumped together. Each is a
        # separate thing somebody has to go and supply.
        for attribute, value in (
            ("owner", item.owner),
            ("due date", item.due),
            ("tracker reference", item.tracker_ref),
            ("category", item.category),
        ):
            if not value:
                defects.append(
                    Defect(
                        dimension=Dimension.ACTION_ITEM_COMPLETE,
                        detail=f"action item has no {attribute}",
                        quote=item.title,
                    )
                )

    if rca.action_items and not any(
        item.category is Category.PREVENT for item in rca.action_items
    ):
        defects.append(
            Defect(
                dimension=Dimension.HAS_PREVENTIVE_ACTION,
                detail=(
                    "no action item is categorised as preventing recurrence; an RCA "
                    "that only improves detection has accepted the recurrence"
                ),
                quote="; ".join(item.title for item in rca.action_items),
            )
        )

    return defects


def check_structure(rca: RCA, rubric: Rubric, as_of: datetime) -> Review:
    defects: list[Defect] = []

    defects += _timeline_defects(rca, rubric)
    defects += _blameless_defects(rca, rubric)
    defects += _action_item_defects(rca)

    if not HAS_QUANTITY.search(rca.impact):
        defects.append(
            Defect(
                dimension=Dimension.IMPACT_QUANTIFIED,
                detail="impact states no measured quantity",
                quote=rca.impact or "(impact is empty)",
            )
        )

    if len(rca.contributing_factors) < rubric.min_contributing_factors:
        defects.append(
            Defect(
                dimension=Dimension.CONTRIBUTING_FACTORS_PRESENT,
                detail=(
                    f"{len(rca.contributing_factors)} contributing factor(s), rubric "
                    f"expects at least {rubric.min_contributing_factors}"
                ),
                quote="; ".join(rca.contributing_factors) or "(none recorded)",
            )
        )

    return Review(
        rca_id=rca.rca_id,
        defects=tuple(defects),
        # Not zero defects. An incident that produced no follow-up was either
        # trivial or never really reviewed, and which one it is needs a human.
        requires_human_judgement=not rca.action_items,
    )
