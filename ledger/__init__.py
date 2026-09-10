"""Append-only cost ledger, shared by every artifact in this repository.

Deliberately a JSONL file rather than a service. It is greppable, diffable,
needs nothing running, and is honest about being a local artifact rather than
pretending to be a platform.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


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
            "cost": cost,
            # What the decision assessed. Without it the cost of a decision is
            # recorded but not what it was for, so spend cannot be summed per
            # dimension and row order becomes the only way to tell them apart.
            "rubric": rubric,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")

    def cost_of(self, decision_id: str) -> float:
        """Total spend across every call belonging to one decision."""
        if not self.path.exists():
            return 0.0
        total = 0.0
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            # Unknown keys are ignored rather than rejected, so the record can
            # grow without breaking readers written against an older shape.
            entry = json.loads(line)
            if entry.get("decision_id") == decision_id:
                total += entry.get("cost", 0.0)
        return total
