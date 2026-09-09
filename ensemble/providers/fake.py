"""Deterministic test double. Scripted verdicts, no network, no keys."""

import threading
from dataclasses import dataclass, field

from ..types import EvidenceBundle, JudgeVerdict, RaterVerdict, Rubric
from . import Usage


@dataclass
class FakeProvider:
    grades: dict[str, str]
    justified: bool = True
    rater_reasoning: str = "because"
    fail_models: frozenset[str] = frozenset()
    barrier: threading.Barrier | None = None
    judge_calls: list[dict] = field(default_factory=list)

    def grade(
        self, rubric: Rubric, evidence: EvidenceBundle, model: str
    ) -> tuple[RaterVerdict | None, Usage]:
        if self.barrier is not None:
            # Both raters must arrive before either proceeds. Serial execution
            # cannot satisfy this, which is what makes the concurrency test
            # deterministic rather than a timing guess.
            self.barrier.wait()

        if model in self.fail_models:
            return None, Usage()

        return (
            RaterVerdict(
                rater=model, grade=self.grades[model], reasoning=self.rater_reasoning
            ),
            Usage(input_tokens=1200, output_tokens=300, cost=0.0135),
        )

    def judge(
        self, rubric: Rubric, evidence: EvidenceBundle, grade: str, model: str
    ) -> tuple[JudgeVerdict | None, Usage]:
        # Recorded so a test can assert no rater output reached it.
        self.judge_calls.append(
            {
                "rubric": rubric.name,
                "subject": evidence.subject,
                "grade": grade,
                "judge_model": model,
            }
        )
        return (
            JudgeVerdict(justified=self.justified, reasoning="fake judge verdict"),
            Usage(input_tokens=900, output_tokens=200, cost=0.0038),
        )
