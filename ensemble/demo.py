"""One real decision across two providers.

The only thing in this repository that spends money. Everything else, including
every test, runs offline against the fake provider.

Put your keys in `.env` at the repository root (copy `.env.example`), or export
them. Then:

    python -m ensemble.demo

Models are overridable, because nothing here should hardcode a vendor:

    RATER_A=anthropic/claude-opus-5 RATER_B=gemini/gemini-3.8-flash python -m ensemble.demo
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from ledger import Ledger

from .env import load_env
from .gate import Decision
from .orchestrator import Rater, run_decision
from .report import format_halt_report
from .types import EvidenceBundle, EvidenceRecord, Rubric

# Defaults only. The environment is read inside main(), after .env is loaded,
# because a module-level read happens at import time and would silently ignore
# anything the file sets.
DEFAULT_RATER_A = "anthropic/claude-opus-5"
DEFAULT_RATER_B = "gemini/gemini-3.8-flash"
DEFAULT_JUDGE = "anthropic/claude-sonnet-5"

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
    load_env()
    missing = [k for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY") if not os.environ.get(k)]
    if missing:
        print(f"Set {' and '.join(missing)} first. See the module docstring.")
        return 1

    try:
        from .providers.litellm import LiteLLMProvider
    except ImportError:
        print('litellm is not installed. Run: pip install -e ".[providers]"')
        return 1

    rater_a = os.environ.get("RATER_A", DEFAULT_RATER_A)
    rater_b = os.environ.get("RATER_B", DEFAULT_RATER_B)
    judge = os.environ.get("JUDGE", DEFAULT_JUDGE)

    provider = LiteLLMProvider()
    ledger = Ledger(Path(".ledger/calls.jsonl"))

    print(f"Raters:  {rater_a}\n         {rater_b}\nJudge:   {judge}\n")

    result = run_decision(
        rubric=RUBRIC,
        evidence=EVIDENCE,
        raters=[Rater(provider, rater_a), Rater(provider, rater_b)],
        judge=Rater(provider, judge),
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
