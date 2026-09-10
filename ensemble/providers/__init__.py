"""The seam every model call goes through.

The protocol lives here rather than in a vendor library so that `ensemble`
stays importable, and fully testable, with no provider package installed. That
is what keeps the governance claim verifiable for free.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from ..types import EvidenceBundle, JudgeVerdict, RaterVerdict, Rubric

# Anything key-shaped is removed from a message before an operator sees it.
# Defensive rather than evidence-driven: provider errors are vendor text, but
# the cost of being wrong once is a credential in a terminal or a log.
_KEYISH = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|AQ\.[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{16,})"
)


def redact(message: str) -> str:
    return _KEYISH.sub("[REDACTED]", message)


@dataclass(frozen=True)
class Usage:
    """What one model call consumed. Feeds the cost ledger."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@dataclass(frozen=True)
class Call:
    """The outcome of one model call.

    A failure carries its reason. The first live run of this repository halted
    three dimensions and told the operator "assessors did not agree", when in
    fact every call had errored and the reason was known and discarded. A halt is
    a claim, and Principle II applies to it.
    """

    verdict: RaterVerdict | JudgeVerdict | None
    usage: Usage
    error: str | None = None

    @property
    def failed(self) -> bool:
        return self.verdict is None


class Provider(Protocol):
    """Contract obligations on any implementation:

    - `judge` MUST NOT be passed rater verdicts, and MUST NOT be able to
      observe them. Note there is no parameter through which it could.
    - A failure MUST surface as a `Call` with no verdict and a populated
      `error`, never as a fabricated verdict. Returning a plausible default on
      error is the exact failure this repository exists to prevent.
    - A message in `error` MUST have been passed through `redact`.
    """

    def grade(self, rubric: Rubric, evidence: EvidenceBundle, model: str) -> Call: ...

    def judge(
        self, rubric: Rubric, evidence: EvidenceBundle, grade: str, model: str
    ) -> Call: ...
