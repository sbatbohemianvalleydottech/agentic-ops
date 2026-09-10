"""Have an agent draft an RCA from raw incident artifacts, then review what it wrote.

Drafting is deliberately not a feature of this package. An agent-written RCA is
precisely the artifact the eval exists to doubt, and shipping it as a capability
would be claiming the opposite. It ships as a demo because watching the eval mark
its own drafter down is the clearest statement of what the eval is for.

    export ANTHROPIC_API_KEY=... GEMINI_API_KEY=...
    python -m rca_agent.draft
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from ledger import Ledger

from .report import render_review
from .rubric import load_rubric
from .structure import check_structure
from .types import load_rca

DRAFTER = os.environ.get("DRAFTER", "anthropic/claude-opus-5")
AS_OF = datetime(2026, 9, 1)

# Raw material only. No conclusions, no framing, nothing that hands the drafter
# an answer. Whether it reaches the cause or stops at the trigger is the point.
ARTIFACTS = """
ALERTS
  02:14:07  api-gateway p99 latency 4.2s (threshold 800ms)
  02:14:41  checkout-service error rate 11% (threshold 2%)
  02:19:02  api-gateway healthcheck failing on 3 of 8 instances

DEPLOY LOG
  01:58:22  checkout-service v4.11.0 -> v4.12.0 (rolling, 8 instances)
  02:31:44  checkout-service v4.12.0 -> v4.11.0 (rollback, operator initiated)

INCIDENT CHANNEL
  02:16  ines: getting paged on checkout, anyone deploying?
  02:17  tom: 4.12.0 went out about 20 min ago
  02:21  ines: pool exhaustion in the logs, 4.12 bumped max_connections?
  02:23  tom: it did, 20 -> 50 per instance. db max is 200 and we run 8 instances
  02:24  ines: so 400 requested against a 200 limit
  02:29  tom: rolling back
  02:31  tom: rollback started
  02:38  ines: latency recovering
  02:44  ines: error rate back to baseline

POST-INCIDENT NOTES
  no staging test covers connection pool sizing
  db max_connections is not referenced anywhere in service config
  the change passed review; two approvals
"""

SCHEMA_HINT = """Reply with JSON only, matching this shape:
{"rca_id": "...", "severity": "...",
 "timeline": [{"name": "detection|escalation|mitigation|resolution", "at": "ISO8601"}],
 "impact": "...", "stated_cause": "...", "contributing_factors": ["..."],
 "narrative": "...", "participants": ["..."],
 "action_items": [{"title": "...", "owner": "...", "due": "ISO8601",
                   "tracker_ref": "...", "category": "prevent|prepare|process|comms",
                   "state": "open", "created": "ISO8601"}],
 "closed_at": "ISO8601", "followups_exported_at": "ISO8601"}"""


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first. See the module docstring.")
        return 1

    try:
        from litellm import completion
    except ImportError:
        print('litellm not installed. Run: pip install -e ".[providers]"')
        return 1

    print(f"Drafting with {DRAFTER}...\n")

    response = completion(
        model=DRAFTER,
        messages=[
            {
                "role": "user",
                "content": (
                    "Write an incident review from these artifacts.\n"
                    f"{ARTIFACTS}\n{SCHEMA_HINT}"
                ),
            }
        ],
        response_format={"type": "json_object"},
    )

    drafted = Path(".drafted-rca.json")
    drafted.write_text(response.choices[0].message.content)

    rca = load_rca(drafted)
    review = check_structure(rca, load_rubric(), AS_OF)

    print(f"Stated cause: {rca.stated_cause}\n")
    print(render_review(review))

    print(
        "\nThe question worth asking of the output above: does the stated cause "
        "explain why a change requesting 400 connections against a limit of 200 "
        "reached production with two approvals, or does it stop at the change "
        "itself? Run with --judgement to have that assessed rather than assumed.\n"
        f"Draft saved to {drafted}."
    )

    ledger = Ledger(Path(".ledger/calls.jsonl"))
    ledger.record(
        decision_id="draft-demo", caller="rca_agent.draft", model=DRAFTER,
        role="drafter",
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        cost=0.0,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
