# ensemble

Multi-model grading with a halt gate. No judgement that matters gets made by a
single model, and disagreement halts rather than averages.

This package is standalone. It knows nothing about performance reviews, cloud
costs or incident reports; those are callers. It imports nothing from any agent
package, and a test enforces that.

## The problem it solves

An agent's most dangerous failure is not a crash. It is a confident wrong answer
returned successfully, because nothing downstream can tell it apart from a
correct one.

Two models agreeing is the usual defence. It is not enough. Models sharing a
training lineage fail in correlated ways, so the case where both are wrong in
the same direction is exactly the case a comparison passes.

So there are two independent raters **and** a judge that never sees whether they
agreed, answering a different question: is this grade justified by this evidence
under this rubric?

```
raters agree   AND judge: justified    -> PROCEED
raters differ                          -> HALT  disagreement
raters agree   AND judge: unjustified  -> HALT  correlated failure
a verdict is missing                   -> HALT  incomplete
a grade is off the rubric's scale      -> HALT  invalid verdict
```

The third row is why a judge exists. If the check were only whether two grades
match, `a == b` would do it and a third model would be decoration.

## Use it

```python
from ensemble.orchestrator import Rater, run_decision
from ensemble.providers.litellm import LiteLLMProvider
from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric
from ledger import Ledger

provider = LiteLLMProvider()

result = run_decision(
    rubric=Rubric(
        name="performance",
        criteria="assess the year against the rubric",
        scale=("not meeting", "meeting", "exceeding"),
    ),
    evidence=EvidenceBundle(subject="engineer-07", records=(...,)),
    raters=[
        Rater(provider, "anthropic/claude-opus-5"),
        Rater(provider, "gemini/gemini-2.5-pro"),
    ],
    judge=Rater(provider, "anthropic/claude-sonnet-5"),
    ledger=Ledger(Path(".ledger/calls.jsonl")),
    caller="perf-review",
)

if result.decision is not Decision.PROCEED:
    print(format_halt_report(result))   # then a human decides
```

Raters from two different providers is the point, not a flourish. Shared
training lineage is what makes correlated failure likely, and it makes vendor
concentration a configuration line rather than a rewrite.

## Run it on its own

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest
```

Everything passes offline against the fake provider. **No API key is needed for
any test.** If one ever is, the gate has stopped being auditable for free, which
is the property worth protecting, and the CI job checks for it.

## Dependencies

Nothing, for the core. `ensemble` and `ledger` import only the standard library,
so the governance claim can be audited by reading `gate.py` and verified without
spending anything.

`ensemble.providers.litellm` needs `litellm`, installed with
`pip install -e ".[providers]"`. Importing it fails without that. Importing
`ensemble` does not.

LiteLLM is the seam because it is what the model gateway this work targets already
runs, so the artifact speaks the platform's interface rather than sitting beside
it.

## Design notes worth knowing before you change it

- **`evaluate_gate` is pure.** No clock, no network, no I/O. That is deliberate:
  it means the whole governance claim can be read in one function and tested
  exhaustively for free. Keep it that way.
- **A single rater raises rather than halting.** A halt is something a caller
  might retry. Retrying a single-rater decision would quietly produce the
  one-model judgement the package exists to prevent.
- **Precedence is fixed**, because several conditions can hold at once and which
  one a human is told about changes what they do next. See
  `specs/001-ensemble-halt-gate/data-model.md`.
- **A missing verdict is never agreement.** The dangerous default is proceeding
  on the survivors, which halves the guarantee at the moment something is
  already wrong.
- **Nothing is averaged, rounded, or decided by majority.** Two against one is a
  disagreement.
- **A provider failure returns no verdict, never a plausible default.**
