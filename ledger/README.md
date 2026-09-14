# ledger

An append-only record of what every model call cost, one JSON line per call, so the cost
of any decision can be worked out afterwards.

**Run every command here from the repository root**, one level above this folder, because
`.venv` and `.ledger/` resolve from there. If the project is not set up yet,
[TRY-IT.md](../TRY-IT.md) does that in two commands and says which Python it needs.

## Why it exists

A decision made by three models has a price, and nobody can manage what nobody records.
Every paid path in this repository writes here, so "what did that judgement cost" is a
question with an answer rather than an estimate. The
[constitution](../.specify/memory/constitution.md) requires it: every model call is metered.

It is a file rather than a service on purpose. It is greppable and diffable, needs nothing
running, and does not pretend to be a platform.

## Run it

Save this as `/tmp/try_ledger.py` and run `.venv/bin/python /tmp/try_ledger.py` from the
repository root:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from ledger import Ledger

with TemporaryDirectory() as tmp:
    ledger = Ledger(Path(tmp) / "calls.jsonl")

    # One decision, three calls: two raters and the judge.
    for role, model, cost in [
        ("rater", "anthropic/claude-opus-5", 0.0182),
        ("rater", "gemini/gemini-3.8-flash", 0.0009),
        ("judge", "anthropic/claude-sonnet-5", 0.0041),
    ]:
        ledger.record(
            decision_id="d1", caller="rca_agent:rca-hollow", model=model, role=role,
            input_tokens=870, output_tokens=257, cost=cost, rubric="cause_not_trigger",
        )

    print(ledger.cost_of("d1"))            # the whole decision
    print(ledger.cost_of("d2"))            # a decision with no calls
    print(ledger.path.read_text().strip().count("\n") + 1, "lines")
```

```
0.0232
0
3 lines
```

Exactly `0.0232`, not `0.023200000000000002`. LiteLLM returns a float and that is out of
this package's hands, but it stops being one here: costs are rounded to ten places on the
way in, which keeps a millionth of a cent and drops the binary noise, and totals are summed
as `Decimal`. `cost_agent` has always used `Decimal` for the same money, and this now
matches it rather than quietly differing.

After a paid run, the committed agents write to `.ledger/calls.jsonl` and the same file
answers the question directly:

```bash
.venv/bin/python -c "import json,collections; c=collections.Counter(); \
[c.update({json.loads(l).get('rubric'): json.loads(l)['cost']}) for l in open('.ledger/calls.jsonl')]; \
print(c)"
```

**That file is gitignored, so on a fresh checkout it does not exist** and the command above
raises `FileNotFoundError`. That is the correct answer to "what have I spent" before
spending anything, but it is a traceback rather than a sentence, so expect it.

## How it works

Each line holds the decision, the caller, the model and its role, the token counts, the
cost, the rubric being assessed and a UTC timestamp. Lines are only ever appended. A reader
ignores keys it does not recognise, so the format can grow without breaking older readers,
and `rubric` is optional, so rows written before that field existed still parse.

What writes to it:

- [`ensemble`](../ensemble/README.md) writes a line for every rater and judge call, failed
  calls included.
- `python -m rca_agent.draft`, a demo, writes one line for its drafting call.
- The probes that run before every paid pass, one minimal call per model, write one line
  each under the decision id `preflight`, failed probes included. Lifetime probe spend is
  `Ledger(DEFAULT_PATH).cost_of("preflight")`.

## What you can argue with

The fields. A row records tokens, cost, the rubric assessed and the version of the prompt
set that produced the verdict, and deliberately not the
model's reasoning text, which can be large and is rendered into the report instead. If you
want cost attributed by team or by service rather than by caller, that is a field here and
nothing else changes.

## The paid path

None. This package spends nothing. It records what other things spent.

## What it does not do

- **No aggregation, no dashboard, no retention policy.** It is a file, and `jq` or three
  lines of Python answer most questions of it.
- **It cannot prove a call is missing.** Every writer in this repository is wired to it
  and a test covers each, but nothing detects a future caller that forgets. The constitution
  says every model call is metered; this file can only show what was.
- **No concurrency guarantees** beyond append-mode writes from one process.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_ledger.py tests/unit/test_money_is_exact.py \
  tests/contract/test_imports.py
```

19 tests, offline, no credentials.

`tests/contract/test_imports.py` is the one enforcing that this package imports nothing
from an agent, so the dependency claim below is checked on every build rather than asserted.

## Dependencies

Standard library only.
