"""The seam every model call goes through.

The protocol lives here rather than in a vendor library so that `ensemble`
stays importable, and fully testable, with no provider package installed. That
is what keeps the governance claim verifiable for free.
"""

from dataclasses import dataclass
from typing import Protocol

from ..types import EvidenceBundle, JudgeVerdict, RaterVerdict, Rubric


@dataclass(frozen=True)
class Usage:
    """What one model call consumed. Feeds the cost ledger."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class Provider(Protocol):
    """Contract obligations on any implementation:

    - `judge` MUST NOT be passed rater verdicts, and MUST NOT be able to
      observe them. Note there is no parameter through which it could.
    - A failure MUST surface as a `None` verdict, never as a fabricated one.
      Returning a plausible default on error is the exact failure this
      repository exists to prevent.
    """

    def grade(
        self, rubric: Rubric, evidence: EvidenceBundle, model: str
    ) -> tuple[RaterVerdict | None, Usage]: ...

    def judge(
        self, rubric: Rubric, evidence: EvidenceBundle, grade: str, model: str
    ) -> tuple[JudgeVerdict | None, Usage]: ...
