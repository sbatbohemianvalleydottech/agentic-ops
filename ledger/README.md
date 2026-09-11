# ledger

An append-only record of what every model call cost, one JSON line per call, so the cost
of any decision can be worked out afterwards.

It is a file rather than a service on purpose. It is greppable and diffable, needs nothing
running, and does not pretend to be a platform.

## Use it

```python
from pathlib import Path

from ledger import Ledger

ledger = Ledger(Path(".ledger/calls.jsonl"))
ledger.record(
    decision_id="d1",
    caller="rca_agent:rca-hollow",
    model="anthropic/claude-sonnet-5",
    role="judge",
    input_tokens=870,
    output_tokens=257,
    cost=0.0041,
    rubric="cause_not_trigger",
)
print(ledger.cost_of("d1"))   # every call in that decision, summed
```

Each line holds the decision, the caller, the model and its role, the token counts, the
cost, the rubric being assessed and a UTC timestamp. Lines are only ever appended. A reader
ignores keys it does not recognise, so the format can grow without breaking older readers,
and `rubric` is optional so rows written before it existed still parse.

## What writes to it

- `ensemble` writes a line for every rater and judge call, failed calls included.
- `python -m rca_agent.draft`, a demo, writes one line for its drafting call, with the cost
  recorded as zero.
- The probes that run before a paid pass, one call per model, write nothing.

The last two fall short of the constitution, which says every model call must be metered.

Both agents keep the file at `.ledger/calls.jsonl`, which is gitignored.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_ledger.py
```

## Dependencies

Standard library only. Nothing here imports from an agent, and the contract test fails CI
if that changes.
