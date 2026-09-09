from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EvidenceRecord:
    """One piece of material a decision is made from.

    Every claim in any verdict must be traceable to one of these, which is why
    the reference is mandatory rather than nice to have.
    """

    source: str
    timestamp: datetime
    ref: str
    content: str

    def __post_init__(self):
        if not self.ref.strip():
            raise ValueError(
                f"evidence from {self.source!r} needs a resolvable ref; a claim citing it "
                "could not be checked"
            )


@dataclass(frozen=True)
class EvidenceBundle:
    """The material behind one decision, and who or what it concerns."""

    subject: str
    records: tuple[EvidenceRecord, ...]


@dataclass(frozen=True)
class Rubric:
    """The criteria and grade scale a decision is assessed against.

    Supplied by the calling agent, because different agents grade different
    things. Scale order is meaningful for reporting and never for arithmetic.
    """

    name: str
    criteria: str
    scale: tuple[str, ...]

    def __post_init__(self):
        if len(set(self.scale)) < 2:
            raise ValueError(
                f"rubric {self.name!r} needs at least two distinct grades, got {self.scale!r}"
            )


@dataclass(frozen=True)
class RaterVerdict:
    """One model's independent grade, with the reasoning it gave."""

    rater: str
    grade: str
    reasoning: str


@dataclass(frozen=True)
class JudgeVerdict:
    """The judge's independent view of whether a grade is justified.

    The judge never sees whether the raters agreed. It answers a different
    question: does the evidence support this grade under this rubric?
    """

    justified: bool
    reasoning: str
