"""One real decision across two providers.

The only thing in this repository that spends money. Everything else, including
every test, runs offline against the fake provider.

    export ANTHROPIC_API_KEY=...
    export GEMINI_API_KEY=...
    python -m ensemble.demo

Models are overridable, because nothing here should hardcode a vendor:

    RATER_A=anthropic/claude-opus-5 RATER_B=gemini/gemini-2.5-pro python -m ensemble.demo
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from ledger import Ledger

from .gate import Decision
from .orchestrator import Rater, run_decision
from .report import format_halt_report
from .types import EvidenceBundle, EvidenceRecord, Rubric

RATER_A = os.environ.get("RATER_A", "anthropic/claude-opus-5")
RATER_B = os.environ.get("RATER_B", "gemini/gemini-2.5-pro")
JUDGE = os.environ.get("JUDGE", "anthropic/claude-sonnet-5")

RUBRIC = Rubric(
    name="performance",
    criteria=(
        "Assess this engineer's year. Weigh delivered impact over activity. "
        "Volume of tickets is not itself evidence of impact."
    ),
    scale=("not meeting", "meeting", "exceeding"),
)

# Deliberately thin evidence dressed up as impressive. Plenty of activity,
# little demonstrated impact. It is the shape of input that tempts two models
# into the same wrong answer, which is what the judge is there to catch.
EVIDENCE = EvidenceBundle(
    subject="engineer-07",
    records=(
        EvidenceRecord(
            source="jira",
            timestamp=datetime(2026, 2, 11),
            ref="PLATFORM-412",
            content="Closed 94 tickets this quarter, the highest on the team.",
        ),
        EvidenceRecord(
            source="github",
            timestamp=datetime(2026, 4, 2),
            ref="PR-2871",
            content="312 pull requests merged, mostly dependency bumps.",
        ),
        EvidenceRecord(
            source="confluence",
            timestamp=datetime(2026, 5, 20),
            ref="WIKI-88",
            content="Wrote the on-call runbook. No record of it being used or reviewed.",
        ),
    ),
)


def main() -> int:
    missing = [k for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY") if not os.environ.get(k)]
    if missing:
        print(f"Set {' and '.join(missing)} first. See the module docstring.")
        return 1

    try:
        from .providers.litellm import LiteLLMProvider
    except ImportError:
        print('litellm is not installed. Run: pip install -e ".[providers]"')
        return 1

    provider = LiteLLMProvider()
    ledger = Ledger(Path(".ledger/calls.jsonl"))

    print(f"Raters:  {RATER_A}\n         {RATER_B}\nJudge:   {JUDGE}\n")

    result = run_decision(
        rubric=RUBRIC,
        evidence=EVIDENCE,
        raters=[Rater(provider, RATER_A), Rater(provider, RATER_B)],
        judge=Rater(provider, JUDGE),
        ledger=ledger,
        caller="demo",
    )

    if result.decision is Decision.PROCEED:
        print(f"PROCEED with grade: {result.grade}\n")
        for verdict in result.raters:
            print(f"  {verdict.rater} -> {verdict.grade}\n    {verdict.reasoning}\n")
    else:
        print(format_halt_report(result))

    print(f"\nDecision {result.decision_id} cost ${ledger.cost_of(result.decision_id):.4f}")
    print("Ledger: .ledger/calls.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
