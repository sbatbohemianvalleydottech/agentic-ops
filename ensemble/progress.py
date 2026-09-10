"""Telling the operator a run is alive.

Plain lines on stderr. No terminal control codes, no spinner, no carriage
returns: the output has to be as readable in a CI log or a piped file as in a
terminal, and a spinner is neither.

Progress is for humans. Machine-readable run telemetry is the ledger's job and
is not duplicated here.
"""

import sys
from dataclasses import dataclass
from typing import Protocol


class Progress(Protocol):
    def step(self, label: str, cost: float) -> None: ...


@dataclass
class StderrProgress:
    """One line per completed unit of work, with the running cost.

    Cost is on every line deliberately. A run that is working and a run that is
    quietly burning money look identical otherwise, and the second is the one
    you want to catch early.
    """

    total_cost: float = 0.0

    def step(self, label: str, cost: float) -> None:
        self.total_cost += cost
        print(
            f"  ... {label}  (${self.total_cost:.4f} so far)",
            file=sys.stderr,
            flush=True,
        )


class SilentProgress:
    """The default. A deterministic run makes no model calls and has nothing to
    report, so it should print nothing at all."""

    def step(self, label: str, cost: float) -> None:
        return None
