from .gate import Decision, GateResult

_WHY = {
    Decision.HALT_DISAGREEMENT: (
        "Raters assigned different grades. No majority was taken and nothing was "
        "averaged, because a split is the signal that this needs you."
    ),
    Decision.HALT_CORRELATED_FAILURE: (
        "Every rater agreed, and the judge does not think the evidence supports "
        "that grade. Agreement between models is not agreement with the facts."
    ),
    Decision.HALT_INVALID_VERDICT: (
        "A rater returned a grade that is not on the rubric's scale. This is more "
        "likely a broken prompt or a changed provider than a judgement call."
    ),
    Decision.HALT_INCOMPLETE: (
        "An expected verdict is missing. The remaining verdicts were not treated "
        "as unanimous, because absence is not agreement."
    ),
}


def format_halt_report(result: GateResult) -> str:
    """Render a halted decision for the human who now has to make the call.

    Every position is reproduced in full. Nothing is truncated or summarised,
    because the report is all the human gets and tidiness here costs them the
    detail they need.
    """
    lines = [
        f"DECISION: {result.decision.value}",
        "",
        _WHY.get(result.decision, "This decision did not pass the gate."),
        "",
        "Rater positions:",
    ]

    for verdict in result.raters:
        lines += [f"  {verdict.rater} -> {verdict.grade}", f"    {verdict.reasoning}", ""]

    if result.failures:
        # The reason the run produced nothing, rather than leaving the operator
        # to infer it from vendor output. This section exists because the first
        # live run reported disagreement when in fact every call had errored.
        lines += ["", "Calls that produced no verdict:"]
        for failure in result.failures:
            lines += [
                f"  {failure.role} {failure.model}",
                f"    {failure.reason}",
            ]
        lines.append("")

    if result.judge is None:
        lines.append("Judge: no verdict returned.")
    else:
        verdict = "justified" if result.judge.justified else "not justified"
        lines += [f"Judge: {verdict}", f"  {result.judge.reasoning}"]

    lines += ["", "Nothing has been recorded. The next move is yours."]
    return "\n".join(lines)
