# ensemble

Multi-model grading with a halt gate. No judgement that matters gets made by a single
model, and disagreement halts rather than averages.

This package is standalone. It knows nothing about performance reviews, cloud costs or
incident reports; those are callers. It imports nothing from any agent package, which
`tests/contract/test_imports.py` enforces on every build.

**Run every command here from the repository root**, one level above this folder, because
`.venv` and `tests/` live there. If the project is not set up yet, [TRY-IT.md](../TRY-IT.md)
does that in two commands and says which Python it needs.

## Why it exists

An agent's most dangerous failure is not a crash. It is a confident wrong answer returned
successfully, because nothing downstream can tell it apart from a correct one.

Two models agreeing is the usual defence. It is not enough. Models sharing a training
lineage fail in correlated ways, so the case where both are wrong in the same direction is
exactly the case a comparison passes.

So there are two independent raters **and** a judge that never sees whether they agreed,
answering a different question: is this grade justified by this evidence under this rubric?

The gate checks these in order, and the first line that matches decides:

```
fewer than two raters                  -> refuses to run, this is a misconfiguration
a verdict is missing                   -> HALT  incomplete
a grade is off the rubric's scale      -> HALT  invalid verdict
raters differ                          -> HALT  disagreement
raters agree   AND judge: unjustified  -> HALT  correlated failure
raters agree   AND judge: justified    -> PROCEED
```

The order matters as much as the rules, because several conditions can hold at once and
which one a human is told about changes what they do next. Absence is checked first:
every rule below it would otherwise read a partial ensemble as a healthy one.

The second-to-last line is why a judge exists. If the check were only whether two grades
match, `a == b` would do it and a third model would be decoration.

## Run it

The gate works offline, with no key and no spend, against the deterministic fake provider
the whole test suite uses:

```bash
.venv/bin/python - <<'PY'
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ensemble.orchestrator import Rater, run_decision
from ensemble.providers.fake import FakeProvider
from ensemble.report import format_halt_report
from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric
from ledger import Ledger

rubric = Rubric(name="performance", criteria="assess the year",
                scale=("not meeting", "meeting", "exceeding"))
evidence = EvidenceBundle(subject="engineer-07", records=(
    EvidenceRecord(source="1:1 notes", timestamp=datetime(2026, 3, 4, tzinfo=UTC),
                   ref="notes/2026-03-04.md", content="Led the storage migration."),
))

# The two raters disagree. Nothing here averages them.
provider = FakeProvider(grades={"model-a": "meeting", "model-b": "exceeding"})

with TemporaryDirectory() as tmp:
    calls = Path(tmp) / "calls.jsonl"
    result = run_decision(
        rubric=rubric, evidence=evidence,
        raters=[Rater(provider, "model-a"), Rater(provider, "model-b")],
        judge=Rater(provider, "model-judge"),
        ledger=Ledger(calls), caller="readme",
    )
    print(result.decision, "\n")
    print(format_halt_report(result))
    print(f"\n{len(calls.read_text().splitlines())} calls metered to the ledger, "
          f"costing {Ledger(calls).cost_of(result.decision_id)}")
PY
```

```
Decision.HALT_DISAGREEMENT

DECISION: halt_disagreement

Raters assigned different grades. No majority was taken and nothing was averaged, because a split is the signal that this needs you.

Rater positions:
  model-a -> meeting
    because

  model-b -> exceeding
    because

Judge: justified
  fake judge verdict

Nothing has been recorded. The next move is yours.

3 calls metered to the ledger, costing 0.0308
```

Three calls, not two: the judge is called even though the raters had already split, which
is what keeps its cost independent of the outcome. The reasoning lines read `because`
because that is what the fake provider returns; real providers fill them.

Against real models, only the provider changes. This block is complete on its own:

```python
from ensemble.orchestrator import Rater, run_decision          # noqa: F401
from ensemble.providers.litellm import LiteLLMProvider

provider = LiteLLMProvider()
raters = [Rater(provider, "anthropic/claude-opus-5"),
          Rater(provider, "gemini/gemini-3.8-flash")]
judge = Rater(provider, "anthropic/claude-sonnet-5")
# then call run_decision exactly as above, passing these instead
```

Raters from two different providers is the point, not a flourish. Shared training lineage
is what makes correlated failure likely, and this makes vendor concentration a
configuration line rather than a rewrite.

## How it works

`run_decision` calls both raters in parallel, calls the judge whether or not they agreed,
meters every call to the ledger, and hands the verdicts to a pure function.

- **`evaluate_gate` is pure.** No clock, no network, no I/O. The whole governance claim can
  be read in one function and tested exhaustively for free.
- **The judge is called even when the raters agree.** Calling it only on disagreement would
  make its cost conditional on an outcome and hide regressions in the judge itself.
- **Every call is metered**, including calls that failed, which is the `3 calls metered`
  line above.
- **A provider failure returns no verdict**, never a plausible default.

The precedence above, and why each rule sits where it does, is worked through in
[`specs/001-ensemble-halt-gate/data-model.md`](../specs/001-ensemble-halt-gate/data-model.md).

## What you can argue with

These are decisions, not laws, and each one is a place a reasonable reviewer might differ:

- **Nothing is averaged, rounded, or decided by majority.** Two against one is a
  disagreement, not a result. If you want a majority vote, this is the wrong gate.
- **A single rater raises rather than halting.** A halt is something a caller might retry,
  and retrying a single-rater decision would quietly produce the one-model judgement this
  package exists to prevent. It raises `ValueError`, and the message says why.
- **A missing verdict is never agreement.** The dangerous default is proceeding on the
  survivors, which halves the guarantee at the moment something is already wrong.
- **Two raters and one judge**, rather than five raters and a threshold. Three calls is
  what most judgements are worth; the shape is a constructor argument if you disagree.

## The paid path

```bash
uv pip install -e ".[dev,providers]"
cp .env.example .env      # paste ANTHROPIC_API_KEY and GEMINI_API_KEY
.venv/bin/python -m ensemble.demo
```

Roughly three calls and a few cents, against two vendors. Everything else in this package
runs free.

## What it does not do

- **No retries, no reconciliation, no overrides.** A halt is handed to a human with both
  arguments. Principle V of the constitution puts the next move with a person.
- **No memory across runs.** Each decision is independent, so a disagreement that
  reproduces and one that flaps look identical from here. `rca_agent` records that as a
  known limitation of the pair.
- **No domain knowledge.** Rubrics, evidence and scales come from callers, which is what
  keeps three artifacts from becoming one application in three folders.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_gate.py tests/unit/test_gate_edges.py \
  tests/unit/test_types.py tests/unit/test_providers.py \
  tests/integration/test_orchestrator.py tests/contract/test_imports.py
```

Everything passes offline against the fake provider. **No API key is needed for any test.**
If one ever is, the gate has stopped being auditable for free, which is the property worth
protecting, and CI checks for it. `tests/contract/test_imports.py` is the one enforcing
that this package imports nothing from an agent.

## Dependencies

Nothing, for the core. `ensemble` and `ledger` import only the standard library, so the
governance claim can be audited by reading `gate.py` and verified without spending
anything.

`ensemble.providers.litellm` needs `litellm`, installed with `pip install -e ".[providers]"`.
Importing it fails without that; importing `ensemble` does not. A machine that already has
`litellm` will not see that failure, so check with `uv pip show litellm` before concluding
either way.

LiteLLM is the seam because it is what the model gateway this work targets already runs, so the
artifact speaks the platform's interface rather than sitting beside it.
