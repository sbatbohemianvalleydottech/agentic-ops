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
| **[`ci`](ci/__init__.py)** | One exit-code contract, shared by everything a pipeline can run |
| **[`ensemble`](ensemble/README.md)** | The gate. A pure function over verdicts, plus the orchestrator and provider seam |
| **[`ledger`](ledger/README.md)** | Append-only JSONL cost ledger. What any decision cost, after the fact |
| **[`cost_agent`](cost_agent/README.md)** | Finds the structural reasons a cloud bill is what it is, rather than ranking line items by size |
| **[`rca_agent`](rca_agent/README.md)** | Catches the incident review that reads well and says nothing |
| **[`plan_cost`](plan_cost/README.md)** | Prices a Terraform plan before it merges and blocks in staging, with no model in it |
| **[`setup`](setup/README.md)** | The Claude Code setup this was built with, as steps your own Claude Code can run |

`ensemble` and `ledger` import nothing from any agent. A contract test enforces it, and
discovers agent packages from the directory tree, so an agent added later is covered
without anyone remembering.

**Every artifact exits the same way**, so a pipeline treats them alike: 0 ran and nothing to
stop for, 1 ran and the answer is stop, 2 could not judge. `plan_cost` and `rca_agent` gate;
`cost_agent` reports and never returns 1, because an estate costing money is not a
build-breaking condition. The `gates` job in CI runs all three on every push and asserts every
code. Before it existed, `plan_cost` was a CI gate that had never run in CI, `rca_agent` found
five defective reviews and exited 0, and `cost_agent` answered an unreadable file with a
traceback and exit 1, which a pipeline would have read as a finding.

Every package README follows the same eight sections, so the fifth one you read is navigable
without re-learning where anything is. The three that a pipeline can run add a ninth, **Use it
in CI**, which is identical in shape across all three because the exit-code contract is.

## Run it: 30 seconds, no credentials

Full walkthrough in **[TRY-IT.md](TRY-IT.md)**, where every command was run in a fresh
clone before it was written down.

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest                    # 444 passed, 7 skipped, ~0.4s

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

The default install deliberately leaves the provider library out, so **the paid paths need
one more install**. Skip it and every paid command stops with `litellm is not installed`:

```bash
uv pip install -e ".[dev,providers]"   # adds litellm; the suite goes 444+7 -> 451
cp .env.example .env                   # then paste your keys into .env
```

`.env` is gitignored. An exported shell variable always beats it, and an empty value in the
file means "not set" rather than "set to nothing". This is local convenience, **not a
secrets management strategy**.

```bash
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/corpus --check   # ~$0.0003
```

`--check` reports what each configured model answered. It also runs automatically before
every paid pass, so a dead model or an unfunded account costs about $0.0003 to discover
instead of a full run. Every probe is metered like any other call.

Each paid command below is complete as written. Costs are what they charged on
14 September 2026, not estimates:

```bash
.venv/bin/python -m ensemble.demo                              # 3 calls + probes, ~$0.022

.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json \
  --as-of 2026-09-01 --confidence                              # 12 calls, ~$0.13, ~85s

mkdir -p /tmp/one && cp rca_agent/fixtures/corpus/rca-hollow.json /tmp/one/
.venv/bin/python -m rca_agent --corpus /tmp/one \
  --as-of 2026-09-01 --judgement                               # 9 calls, ~$0.09, ~60s
```

`--judgement` assesses every review in the corpus, which is why that one points at a
directory holding a single file rather than at all eight.

Paid passes print progress to stderr with a running cost, so a run that is working and a
run quietly burning money do not look identical. Redirect stdout and the report stays clean.

## How it was built

Spec-driven, through [Spec Kit](https://github.com/github/spec-kit). Every phase is its own
commit: constitution, then specify, plan, tasks, implement, per feature. The
[constitution](.specify/memory/constitution.md) has five principles, two non-negotiable,
and CI enforces the one that is mechanically checkable.

Test-first throughout. No production code without a failing test watched failing first.

**The documents are tested the same way the code is.** Each README is handed to a reader with
no other context, working in a fresh clone, told to run what it says and record where it
breaks. On 14 September that disproved five claims, three of which were defects in the code
rather than in the prose, including a gate that quietly relaxed its own threshold. The
protocol, the prompt and the findings are in **[COLD-READ.md](COLD-READ.md)**.

The decommission feature in `cost_agent` exists because an earlier version filed a platform
with a published sunset date under *right-sizing*: utilisation was the only signal it had
for "should this exist", and the same evidence produced two answers millions apart. The
fix was to take a stated end-of-life date as input rather than infer one.

## What is not here yet

**There is no golden set, and it is the next thing to build.** The gate halts when two raters
disagree, and nothing anywhere measures whether the grade they agreed on was *right*. Every
free path is covered by 451 tests. The paid paths, which are the ones that cost money and make
the judgements, are checked by running them and reading the output.

That matters more than it sounds, because two independent runs of the same fixture on
14 September split on the same 3 of 4 drivers and gave different grades inside them.

**And the obvious fix does not exist.** Pinning `temperature` would make runs comparable, and
neither vendor allows it: Anthropic's Opus 5 and Sonnet 5 reject any value but 1, and Gemini 3
has deprecated the parameter. So run-to-run variation cannot be controlled at the API layer on
these models, which makes a labelled baseline the only way left to tell a prompt regression
from noise. Every ledger row now carries the prompt version that produced it, so when the
baseline exists there is something to attribute a change to.

What it needs is the 8 incident fixtures labelled on each judgement dimension by a person, and
a harness that reports agreement against those labels on every prompt or model change. The
harness is a day. **The labels are the reason it is not here: ground truth is a human input,
and inventing it would be exactly the fabrication this repository exists to catch.**

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
  A fifth way to fail was found later by handing this document to someone with no context:
  installing `.[dev]` and going straight to a paid command, with no provider library. The
  credentials section above now names that install first.
- **`plan_cost` has never called a live billing API.** Its catalogue and budget paths were
  built against the current documentation and tested against recorded responses.
- **All fixtures are synthetic.** No real cloud, incident or employee data is present.
