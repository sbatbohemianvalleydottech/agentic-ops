# Try it locally

Every command below was run on 13 September 2026 in a fresh clone of commit `d32e3fe`, and
the outputs quoted are what it printed. Nothing here needs a credential, a cloud account, a
Terraform binary or a model call. The whole walkthrough is about two minutes.

## 1. Clone and install

```bash
git clone https://github.com/sbatbohemianvalleydottech/agentic-ops.git
cd agentic-ops
uv venv && uv pip install -e ".[dev]"
```

No `uv`? Plain venv and pip work, on **Python 3.11 or newer**:

```bash
python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

On macOS, `python3` is usually the system 3.9 and the install will stop. What it says
depends on how old that Python's pip is. A current pip reports the real reason,
`ERROR: Package 'agentic-ops' requires a different Python: 3.9.6 not in '>=3.11'`; the pip
that ships with macOS 3.9.6 is too old for modern editable installs and complains about a
missing `setup.py` instead. Either way the project has refused to install rather than
failing later, and naming a newer interpreter is the whole fix.

## 2. Run the tests

```bash
.venv/bin/python -m pytest -q
# 416 passed, 3 skipped in 0.36s
```

**The three skips are deliberate and worth understanding.** They are the LiteLLM adapter
tests, and they skip because the provider library is an optional extra:

```bash
.venv/bin/python -m pytest -q -rs | grep SKIPPED
# SKIPPED [1] tests/unit/test_providers.py:62: could not import 'litellm'
```

Install the extra and nothing skips:

```bash
uv pip install -e ".[dev,providers]"
.venv/bin/python -m pytest -q
# 419 passed in 1.7s
```

CI runs both arrangements, and the second job fails if any adapter test skips, so "it passed"
cannot quietly mean "it was not run".

## 3. The three artifacts, offline and free

```bash
.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json --as-of 2026-09-01
```

75 lines, exit 0. Structural cost drivers on a synthetic estate. Swap `estate_a` for
`estate_b` and the same code produces a different diagnosis, which is the check against a
tool that has memorised its fixture.

```bash
.venv/bin/python -m rca_agent \
  --corpus rca_agent/fixtures/corpus --as-of 2026-09-01 --completion
```

77 lines, exit 0. Eight incident reviews, structural defects quoted from the documents, then
action item completion across the corpus.

```bash
.venv/bin/python -m plan_cost \
  --plan plan_cost/fixtures/estate/plan.json --env staging
echo $?   # 1
```

A Terraform plan priced at +$432.89 a month, twelve changed resources all accounted for, and
a blocked verdict. This one calls no model at all.

## 4. The gate, every path it has

```bash
P=plan_cost/fixtures/demo/prices.demo.toml
D=plan_cost/fixtures/demo
```

Run each and check `echo $?`:

| Command | Monthly | Exit |
|---|---|---|
| `.venv/bin/python -m plan_cost --plan $D/staging-over-budget.json --prices $P` | +$1,222.60 | **1** blocked |
| `.venv/bin/python -m plan_cost --plan $D/staging-normal.json --prices $P` | +$119.50 | 0 |
| `.venv/bin/python -m plan_cost --plan $D/staging-marginal.json --prices $P` | +$232.50 | 0 |
| `.venv/bin/python -m plan_cost --plan $D/production-over-budget.json --prices $P` | +$1,222.60 | 0, would have blocked |
| `.venv/bin/python -m plan_cost --plan $D/production-normal.json --prices $P` | +$270.10 | 0, over threshold, nothing fired |
| `.venv/bin/python -m plan_cost --plan $D/incident-io-schedule.json --prices $P` | no figure | 0 |
| `.venv/bin/python -m plan_cost --plan $D/incident-io-schedule-no-environment.json --prices $P` | none | **2** refused to judge |

The two over-budget plans are the same three resources and differ only in
`variables.environment`. Same total, same findings, different ending: staging blocks,
production reports and stands aside.

The last one is the refusal path. No environment in the plan and no `--env`, so it will not
judge rather than picking the lenient default. Add `--env staging` and it exits 0.

The rates in `prices.demo.toml` are invented and say so on every row. They are round on
purpose: e2-standard-4 at $0.20 an hour is $146.00 a month, so eight of them is $1,168.00 and
the total can be checked in your head. The shipped table, `plan_cost/prices.toml`, is the
opposite: fewer rows, each carrying the URL it came from and the date it was read.

## 5. The budget changes the answer, not just the wording

`staging-marginal.json` costs $232.50, which sits between the $250.00 in `policy.toml` and
the $200.00 implied by a budget's own lowest alert line:

```bash
.venv/bin/python -m plan_cost --plan $D/staging-marginal.json --prices $P
echo $?   # 0    no, +$232.50 at or under $250.00

.venv/bin/python -m plan_cost --plan $D/staging-marginal.json --prices $P \
  --budget-json plan_cost/fixtures/budget/budgets.json --budget-name platform-monthly
echo $?   # 1    yes, +$232.50 over $200.00
```

That budget file is a saved `gcloud billing budgets list --format=json` response. The tool
reads files the operator produced; it never calls the API itself, so CI needs no credential.

## 6. Refresh prices from the vendor catalogue

```bash
cp plan_cost/prices.toml /tmp/prices.toml
.venv/bin/python -m plan_cost --refresh-prices plan_cost/fixtures/catalogue/skus.json \
  --prices /tmp/prices.toml
diff plan_cost/prices.toml /tmp/prices.toml
```

Two disk rows are added from the catalogue response, and every machine type row is reported
as having no mapping and left byte-identical, because Compute Engine prices cores and memory
as separate SKUs so no single SKU equals an `e2-standard-4`. A row nobody could refresh must
never come out of a refresh looking fresh.

With billing access, the real response comes from:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus" > skus.json
```

## 7. The paid paths, only if you want them

Everything above is free. Three paths spend money, all opt-in: `cost_agent --confidence`,
`rca_agent --judgement`, and `python -m ensemble.demo`. Each routes a genuine judgement
through two independent raters and a blind judge.

They need the provider library, so install that extra first:

```bash
uv pip install -e ".[dev,providers]"
cp .env.example .env      # then paste an Anthropic key and a Google AI Studio key
```

Check the models answer before spending anything on them:

```bash
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/corpus --check
# one minimal call per model, about $0.0003, and it says what a failing run would have
```

**The judged pass assesses every review in the corpus**, so point it at a directory holding
one file unless you want to pay for eight:

```bash
mkdir -p /tmp/one && cp rca_agent/fixtures/corpus/rca-hollow.json /tmp/one/
.venv/bin/python -m rca_agent --corpus /tmp/one --as-of 2026-09-01 --judgement
```

That is three dimensions, each through two independent raters and a blind judge, so nine
calls and about 9 cents: $0.0901 on 14 September 2026. It runs the same one-call-per-model
preflight first, meters it, and aborts before the paid pass if any model is unreachable. Where the raters disagree it halts and prints both
arguments rather than averaging them, which on `rca-hollow` is the whole point of the
repository.

## What to read next

- [`plan_cost/README.md`](plan_cost/README.md), and the demo guide at
  [`plan_cost/fixtures/demo/README.md`](plan_cost/fixtures/demo/README.md)
- [`cost_agent/README.md`](cost_agent/README.md) and [`rca_agent/README.md`](rca_agent/README.md)
- [`setup/README.md`](setup/README.md), the Claude Code setup this was built with, written so
  your own agent can reproduce it
- [`.specify/memory/constitution.md`](.specify/memory/constitution.md), the five rules the
  code is held to, one of which CI enforces
