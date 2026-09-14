"""Action item completion across a corpus.

The figure no individual review surfaces. Six items agreed, five open at ninety
days, and nobody noticed, is a statement about the organisation rather than about
any one incident.
"""

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .rubric import Rubric
from .types import RCA


@dataclass(frozen=True)
class CompletionReport:
    total_items: int
    closed_items: int
    closure_rate: Decimal
    median_open_age_days: int | None
    closed_without_evidence: int
    export_policy_breaches: tuple[str, ...]
    repeated_action_items: tuple[str, ...]


def report_completion(
    corpus: list[RCA], rubric: Rubric, as_of: datetime
) -> CompletionReport:
    items = [item for rca in corpus for item in rca.action_items]
    closed = [item for item in items if item.state == "closed"]
    open_items = [item for item in items if item.state != "closed"]

    open_ages = [(as_of - item.created).days for item in open_items]

    breaches = tuple(
        rca.rca_id
        for rca in corpus
        # An incident nobody has closed cannot have overdue follow-ups.
        if rca.closed_at is not None
        # Neither can one that agreed none. That review has a worse problem and
        # the report already names it separately; calling it an export breach
        # points a reader at tracker hygiene when nobody committed to anything.
        and rca.action_items
        and rca.followups_exported_at is None
        and as_of - rca.closed_at > timedelta(days=rubric.export_window_days)
    )

    # A title appearing in more than one review is evidence the first attempt
    # never landed.
    titles = Counter(
        title
        for rca in corpus
        for title in {item.title for item in rca.action_items}
    )

    return CompletionReport(
        total_items=len(items),
        closed_items=len(closed),
        closure_rate=(
            (Decimal(len(closed)) / Decimal(len(items))).quantize(Decimal("0.01"))
            if items
            else Decimal("0")
        ),
        median_open_age_days=(
            int(statistics.median(open_ages)) if open_ages else None
        ),
        # Counted apart from closed-with-evidence, because "closed" without a
        # reference and "closed" with a merged pull request are different claims
        # wearing the same word.
        closed_without_evidence=sum(1 for item in closed if not item.closure_evidence),
        export_policy_breaches=breaches,
        repeated_action_items=tuple(
            sorted(title for title, count in titles.items() if count > 1)
        ),
    )
