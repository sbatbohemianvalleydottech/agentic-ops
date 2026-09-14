"""Append-only cost ledger, shared by every artifact in this repository.

Deliberately a JSONL file rather than a service. It is greppable, diffable,
needs nothing running, and is honest about being a local artifact rather than
pretending to be a platform.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

# Where every artifact in this repository writes. Named once so three callers
# cannot drift to three different files and each report a partial total.
DEFAULT_PATH = Path(".ledger/calls.jsonl")

# Costs arrive as floats from the provider, computed as price times tokens in
# binary, so a probe that cost 0.00002475 arrives as 2.4750000000000002e-05.
# Ten places keeps a millionth of a cent and drops only the binary noise.
PLACES = 10


@dataclass
class Ledger:
    path: Path

    def record(
        self,
        *,
        decision_id: str,
        caller: str,
        model: str,
        role: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        rubric: str | None = None,
    ) -> None:
        """Append one line for one model call. Never rewrites history."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "decision_id": decision_id,
            "caller": caller,
            "model": model,
            "role": role,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            # Rounded here rather than on the way out, so the file itself is
            # readable and every reader agrees on the figure.
            "cost": round(float(cost), PLACES),
            # What the decision assessed. Without it the cost of a decision is
            # recorded but not what it was for, so spend cannot be summed per
            # dimension and row order becomes the only way to tell them apart.
            "rubric": rubric,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")

    def cost_of(self, decision_id: str) -> Decimal:
        """Total spend across every call belonging to one decision.

        Summed as Decimal. LiteLLM hands back a float and that is out of our
        hands, but it stops being one here, because three calls costing 0.0182,
        0.0009 and 0.0041 added as floats report 0.023200000000000002.
        """
        if not self.path.exists():
            return Decimal("0")
        total = Decimal("0")
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            # Unknown keys are ignored rather than rejected, so the record can
            # grow without breaking readers written against an older shape.
            entry = json.loads(line)
            if entry.get("decision_id") == decision_id:
                # Through str, never float(Decimal(0.0182)), which would carry
                # the binary expansion straight into the total.
                total += Decimal(str(entry.get("cost", 0)))
        return total
