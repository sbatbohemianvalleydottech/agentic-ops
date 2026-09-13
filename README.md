# agentic-ops

Governance primitives for agents that make consequential judgements, two agents built on
them, and one tool that deliberately calls no model at all.

## The failure it exists for

> **An agent's most dangerous failure is not a crash. It is a confident wrong answer
> returned successfully, because nothing downstream can tell it apart from a correct one.**

Two models agreeing is the usual defence, and it is not enough. Models sharing a training
lineage fail in correlated ways, so the case where both are wrong in the same direction is
exactly the case a comparison passes.

So every judgement here goes through two independent raters **and** a judge that never
learns whether they agreed. Disagreement halts. Nothing is averaged, rounded, or decided by
majority. The gate checks these in order, and the first line that matches decides:

```
fewer than two raters                  -> refuses to run, a misconfiguration
a verdict is missing                   -> HALT  incomplete
a grade is off the rubric's scale      -> HALT  invalid verdict
raters differ                          -> HALT  disagreement
raters agree   AND judge: unjustified  -> HALT  correlated failure
raters agree   AND judge: justified    -> PROCEED
```

Absence is checked first: every rule below it would otherwise read a partial ensemble as a
healthy one.

`plan_cost` is the counterexample, and it belongs to the same argument. It prices a
Terraform plan and checks it against fixed rules without calling a model once, because a
price is arithmetic and a missing autoscaling block is a fact about a document. Knowing
when not to reach for a model is the harder half of the claim.

## What is here

| Directory | What it does |
|---|---|
| **[`ensemble`](ensemble/README.md)** | The gate. A pure function over verdicts, plus the orchestrator and provider seam |
| **[`ledger`](ledger/README.md)** | Append-only JSONL cost ledger. What any decision cost, after the fact |
| **[`cost_agent`](cost_agent/README.md)** | Finds the structural reasons a cloud bill is what it is, rather than ranking line items by size |
| **[`rca_agent`](rca_agent/README.md)** | Catches the incident review that reads well and says nothing |
| **[`plan_cost`](plan_cost/README.md)** | Prices a Terraform plan before it merges and blocks in staging, with no model in it |
| **[`setup`](setup/README.md)** | The Claude Code setup this was built with, as steps your own Claude Code can run |

`ensemble` and `ledger` import nothing from any agent. A contract test enforces it, and
discovers agent packages from the directory tree, so an agent added later is covered
without anyone remembering.

Every README follows the same eight sections, so the fifth one you read is navigable
without re-learning where anything is.

## Run it: 30 seconds, no credentials

Full walkthrough in **[TRY-IT.md](TRY-IT.md)**, where every command was run in a fresh
clone before it was written down.

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest                    # 362 tests, ~1.7s

.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json --as-of 2026-09-01

.venv/bin/python -m rca_agent \
  --corpus rca_agent/fixtures/corpus --as-of 2026-09-01 --completion

.venv/bin/python -m plan_cost \
  --plan plan_cost/fixtures/estate/plan.json --env staging   # exits 1, on purpose
```

**Everything worth attacking runs offline and free.** Only genuine judgement costs money.
An incident review missing a detection timestamp does not need a second opinion, and paying
for one would be the tool failing to think.

Swap `estate_a` for `estate_b` and the same code produces a different diagnosis. If both
produced the same drivers, the tool would be recognising its fixture rather than analysing
an estate.

## Credentials, for the paid paths only

```bash
cp .env.example .env      # then paste your keys into .env
```

`.env` is gitignored. An exported shell variable always beats it, and an empty value in the
file means "not set" rather than "set to nothing". This is local convenience, **not a
secrets management strategy**.

```bash
.venv/bin/python -m rca_agent ... --check    # one call per model, ~$0.0003, no work done
```

`--check` reports what each configured model answered. It also runs automatically before
any paid pass, so a dead model or an unfunded account costs about $0.0003 to discover
instead of a full run.

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

The decommission feature in `cost_agent` exists because an earlier version filed a platform
with a published sunset date under *right-sizing*: utilisation was the only signal it had
for "should this exist", and the same evidence produced two answers millions apart. The
fix was to take a stated end-of-life date as input rather than infer one.

## Honest limitations

- **Built in a week.** Not production-tested.
- **AI-built on synthetic data, human reviewed.** Stated plainly rather than implied.
- **The test suite has never made a live model call**, and the paid paths have. Every test
  runs against a deterministic fake provider; the judgement and confidence passes have been
  run for real against Anthropic and Google. "Tested offline" and "verified end to end" are
  different claims, so both are stated rather than one standing in for the other.
- **The first live run took four attempts to get an answer**: a retired model, a
  workspace-scoped key, an unfunded account, and an empty value in `.env` that a library
  loaded behind us. Each cost a full run to find. That is why `--check` exists, and it is a
  fair description of how much of agentic infrastructure is credentials rather than models.
- **`plan_cost` has never called a live billing API.** Its catalogue and budget paths were
  built against the current documentation and tested against recorded responses.
- **All fixtures are synthetic.** No real cloud, incident or employee data is present.
