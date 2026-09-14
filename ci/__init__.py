"""One exit-code contract, shared by everything here that a pipeline can run.

Three artifacts, three CLIs, and until now three different opinions about what
an exit code means. `plan_cost` returned 0, 1 and 2 with care. `rca_agent`
returned 0 whether it found a clean corpus or five defective reviews, so it
could report a problem and pass the build in the same breath. `cost_agent` did
the same. A tool that always exits 0 cannot gate anything, which makes it
unusable in the one place a quality check belongs.

The contract:

    0  OK         Ran, judged, nothing to stop for.
    1  BLOCKED    Ran, judged, and the answer is stop. Only a gate returns this.
    2  UNJUDGED   Could not judge. Never means expensive, never means clean.

**2 is the one that matters.** A bad input, an unreadable file, an ambiguous
threshold and a plan format nobody has checked all land here rather than on 0,
because a pipeline that treats "I could not tell" as "fine" is worse than no
check at all. It is also why 2 is not 1: a broken gate and a failed gate need
different human responses, and collapsing them teaches people to ignore both.

Not everything gates, and nothing here pretends otherwise:

- **Gates** return all three. `plan_cost` always. `rca_agent` when asked with
  `--fail-on-defects`, because a structural defect is objective and a review
  missing a detection timestamp should not close.
- **Reporters** return 0 or 2 only, never 1. `cost_agent` is one. An estate
  costing money is not a build-breaking condition, and inventing a dollar
  threshold so the tool could look like a gate would be dressing up a report.

`Exit` is an `IntEnum`, so `sys.exit(Exit.BLOCKED)` and `return 1` are the same
thing to the shell and a reader can still see which was meant.
"""

from enum import IntEnum

__all__ = ["Exit", "describe"]


class Exit(IntEnum):
    OK = 0
    BLOCKED = 1
    UNJUDGED = 2


_MEANING = {
    Exit.OK: "ran, judged, nothing to stop for",
    Exit.BLOCKED: "ran, judged, and the answer is stop",
    Exit.UNJUDGED: "could not judge; this never means clean",
}


def describe(code: int) -> str:
    """One line for a CI log, so an exit code in a pipeline is not a bare number."""
    try:
        return f"exit {int(code)}: {_MEANING[Exit(code)]}"
    except ValueError:
        return f"exit {int(code)}: not part of this contract"
