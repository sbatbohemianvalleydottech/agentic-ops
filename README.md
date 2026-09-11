# agentic-ops

Governance primitives for agents that make consequential judgements, and two agents built
on them.

## One idea, applied three times

> **An agent's most dangerous failure is not a crash. It is a confident wrong answer
> returned successfully, because nothing downstream can tell it apart from a correct one.**

Two models agreeing is the usual defence, and it is not enough: models sharing a training
lineage fail in correlated ways, so the case where both are wrong in the same direction is
exactly the case a comparison passes.

So every judgement here goes through two independent raters **and** a judge that never
learns whether they agreed. Disagreement halts. Nothing is averaged, rounded, or decided
by majority.

```
raters agree   AND judge: justified    -> PROCEED
raters differ                          -> HALT  disagreement
raters agree   AND judge: unjustified  -> HALT  correlated failure
a verdict is missing                   -> HALT  incomplete
a grade is off the rubric's scale      -> HALT  invalid verdict
```

## What is here

| Directory | What it does |
|---|---|
| **[`ensemble`](ensemble/README.md)** | The gate. A pure function over verdicts, plus the orchestrator and provider seam |
| **[`ledger`](ledger/)** | Append-only JSONL cost ledger. What any decision cost, after the fact |
| **[`cost_agent`](cost_agent/README.md)** | Finds the structural reasons a cloud bill is what it is, rather than ranking line items by size |
| **[`rca_agent`](rca_agent/README.md)** | Catches the incident review that reads well and says nothing |
| **[`setup`](setup/README.md)** | The Claude Code setup this was built with, as steps your own Claude Code can run |

`ensemble` and `ledger` import nothing from either agent. That is enforced by a contract
test which discovers agent packages from the directory tree, so an agent added later is
covered without anyone remembering.

## Run it — 30 seconds, no credentials

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest                    # 219 tests, ~1.5s

.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json --as-of 2026-09-01

.venv/bin/python -m rca_agent \
  --corpus rca_agent/fixtures/corpus --as-of 2026-09-01 --completion
```

**Everything a sceptical reader would attack runs offline and free.** Only genuine
judgement costs money. An RCA missing a detection timestamp does not need a second
opinion, and paying for one would be the tool failing to think.

Swap `estate_a` for `estate_b` to see the same code produce a different diagnosis. If both
estates produced the same drivers, the tool would be recognising its fixture rather than
analysing an estate.

## Credentials, for the paid paths only

```bash
cp .env.example .env      # then paste your keys into .env
```

`.env` is gitignored. An exported shell variable always beats it, and an empty value in the
file means "not set" rather than "set to nothing".

This is local convenience, **not a secrets management strategy**, and nothing here should
be treated as one.

```bash
.venv/bin/python -m rca_agent ... --check    # probes every model, ~$0.0003, no work done
```

`--check` sends one minimal call per configured model and reports what came back. It also
runs automatically before any paid pass, so a dead model or an unfunded account costs a
third of a cent to discover instead of a full run.

```bash
.venv/bin/python -m ensemble.demo                              # ~3 calls, a few cents
.venv/bin/python -m cost_agent ... --confidence
.venv/bin/python -m rca_agent  ... --judgement
```

Paid passes print progress to stderr with a running cost, so a run that is working and a
run quietly burning money do not look identical. Redirect stdout and the report stays clean.

## How it was built

Spec-driven, through [Spec Kit](https://github.com/github/spec-kit). Every phase is its own
commit: constitution, then specify, plan, tasks, implement, per feature. The
[constitution](.specify/memory/constitution.md) has five principles, two non-negotiable,
and CI enforces the one that is mechanically checkable.

Test-first throughout. No production code without a failing test watched failing first.

The Claude Code setup it was built with is in [setup/README.md](setup/README.md): steps
another Claude Code session can run to reproduce it, verified by running them against an
empty profile.

Feature 004 exists because running `cost_agent` on a real estate exposed a gap in my own
taxonomy: it filed a platform with a published sunset date under *right-sizing*, because
utilisation was the only signal it had for "should this exist". That is written up in
[its spec](specs/004-scheduled-decommission/spec.md).

## Honest limitations

- **Built in one week**, for a project. Not production-tested.
- **AI-built on synthetic data, human reviewed.** Stated plainly rather than implied.
- **The test suite has never made a live model call**, and the paid paths have. Every test
  runs against a deterministic fake provider; the judgement and confidence passes have been
  run for real against Anthropic and Google. "Tested offline" and "verified end to end" are
  different claims, so both are stated rather than one standing in for the other.
- **The first live run took four attempts to get an answer**: a retired model, a
  workspace-scoped key, an unfunded account, and an empty value in `.env` that a library
  loaded behind us. Each cost a full run to find. That is why `--check` exists, and it is a
  fair description of how much of agentic infrastructure is credentials rather than models.
- All fixtures are synthetic. No real estate, incident or employee data is present.
