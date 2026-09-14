# Demo plans

Eight plans and two price tables, so you can drive the gate down every path it has,
including all four refusals, without a Terraform binary, a cloud account or a credential.

**The rates in [`prices.demo.toml`](prices.demo.toml) are invented**, and deliberately round
so the arithmetic can be checked in your head: e2-standard-4 at $0.20 an hour is $146.00 a
month at 730 hours, so eight of them is $1,168.00. The shipped table, `plan_cost/prices.toml`,
is the opposite: fewer rows, each carrying the URL it came from and the date it was read.

Every command below uses the demo rates:

```bash
P=plan_cost/fixtures/demo/prices.demo.toml
D=plan_cost/fixtures/demo
```

## What each one does

| Plan | Monthly change | What happens | Exit |
|---|---|---|---|
| `staging-over-budget.json` | +$1,222.60 | a rule fired, over threshold, staging blocks | **1** |
| `staging-normal.json` | +$119.50 | nothing fired, under threshold | 0 |
| `staging-marginal.json` | +$232.50 | under the policy threshold, over the budget's line | 0, or **1** with `--budget-json` |
| `production-over-budget.json` | +$1,222.60 | identical findings, production reports instead | 0 |
| `production-normal.json` | +$270.10 | over threshold, but nothing fired, so no block | 0 |
| `incident-io-schedule.json` | no figure | on-call rota change, nothing is priceable | 0 |
| `incident-io-schedule-no-environment.json` | none | no environment anywhere, so it refuses to judge | **2** |

## The four cost cases

```bash
.venv/bin/python -m plan_cost --plan $D/staging-over-budget.json --prices $P      # exit 1
.venv/bin/python -m plan_cost --plan $D/staging-normal.json --prices $P           # exit 0
.venv/bin/python -m plan_cost --plan $D/production-over-budget.json --prices $P   # exit 0
.venv/bin/python -m plan_cost --plan $D/production-normal.json --prices $P        # exit 0
```

The two over-budget plans hold the same three resources and differ only in
`variables.environment`. Same total, same findings, different ending:

```
DECISION  blocked                                 DECISION  reported, would have blocked in staging
  environment policy   staging blocks               environment policy   production reports
  exit 1                                            exit 0
```

`production-normal.json` is worth a look for the opposite reason. It is **over** the
threshold at $270.10 and still exits 0, because nothing fired. Blocking needs a rule and a
figure, not just a figure, and the decision block names the condition that was missing. It
also prices a worker in `europe-west1` at the European rate, because price keys are regional
and nothing falls back to a neighbouring region's number.

## The budget changes the answer, not just the wording

`staging-marginal.json` costs $232.50, which sits between the $250.00 in `policy.toml` and
the $200.00 implied by the budget's own lowest alert line:

```bash
.venv/bin/python -m plan_cost --plan $D/staging-marginal.json --prices $P
# exit 0    no, +$232.50 at or under $250.00

.venv/bin/python -m plan_cost --plan $D/staging-marginal.json --prices $P \
  --budget-json plan_cost/fixtures/budget/budgets.json --budget-name platform-monthly
# exit 1    yes, +$232.50 over $200.00
#           budget "platform-monthly": $800.00 x 25% = $200.00
```

Which threshold you point it at is the whole decision, which is the argument for taking it
from a budget somebody already owns rather than a number in a config file.

## The non-compute change

`incident-io-schedule.json` is an on-call rota change, modelled on incident.io's own provider
documentation: a rotation moving from weekly to daily handovers with working intervals added,
a schedule replaced because its timezone changed, and a new schedule for payments.

```bash
.venv/bin/python -m plan_cost --plan $D/incident-io-schedule.json --prices $P   # exit 0
```

```
  Monthly change   nothing here can be priced

  Not counted
    not priceable          3   not a cloud resource 3

  3 resource changes, 3 accounted for.
```

No dollar figure at all, rather than `$0.00`. That is the point: a cost tool that reports zero
for a plan it cannot price is indistinguishable from one reporting zero because the change is
free.

## The error path

Exit 2 means the tool could not judge, and it never means expensive. The same plan without
`variables.environment` refuses rather than guessing:

```bash
.venv/bin/python -m plan_cost --plan $D/incident-io-schedule-no-environment.json --prices $P
# exit 2
# plan_cost: no environment to judge: the plan carries no variables.environment, and no
# --env was given. This is not defaulted, because a gate that quietly became a report is
# worse than no gate

.venv/bin/python -m plan_cost --plan $D/incident-io-schedule-no-environment.json --prices $P --env staging
# exit 0
```

The other three ways to reach exit 2 each ship a fixture, so none of them has to be taken
on faith:

```bash
.venv/bin/python -m plan_cost --plan $D/unchecked-format-version.json --prices $P
# exit 2
# plan_cost: plan format version 2.0 has not been checked against this tool, which reads 1.x

.venv/bin/python -m plan_cost --plan $D/staging-normal.json --prices $D/prices.duplicate-row.toml
# exit 2
# plan_cost: two rows carry the key google/machine-type/e2-standard-4/us-central1, so no
# reader can tell which one a total used

.venv/bin/python -m plan_cost --plan $D/staging-normal.json --prices $P \
  --budget-json plan_cost/fixtures/budget/budgets.json
# exit 2
# plan_cost: the response holds 2 budgets (platform-monthly, data-platform-last-period);
# name one with --budget-name rather than having this tool pick
```

None of them prints a dollar figure or a DECISION line. A refusal must not be mistakable
for a verdict, and a test asserts that.

## These are tested, not just written down

Every exit code in the table above is asserted in
[`tests/integration/test_plan_cost_demo.py`](../../../tests/integration/test_plan_cost_demo.py),
so a demo that stops doing what its name says fails the build rather than failing in front of
an audience.
