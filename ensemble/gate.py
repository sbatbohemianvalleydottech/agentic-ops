from dataclasses import dataclass
from enum import Enum


class Decision(Enum):
    PROCEED = "proceed"
    HALT_DISAGREEMENT = "halt_disagreement"
    HALT_CORRELATED_FAILURE = "halt_correlated_failure"


@dataclass(frozen=True)
class GateResult:
    decision: Decision


def evaluate_gate(raters, judge):
    if len({rater.grade for rater in raters}) > 1:
        return GateResult(decision=Decision.HALT_DISAGREEMENT)
    if not judge.justified:
        return GateResult(decision=Decision.HALT_CORRELATED_FAILURE)
    return GateResult(decision=Decision.PROCEED)
