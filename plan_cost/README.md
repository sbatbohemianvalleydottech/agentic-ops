# plan_cost

Prices a Terraform plan before it merges, and blocks in staging, where a fix is still cheap.

**Run every command here from the repository root**, one level above this folder, because
`.venv` and the fixtures resolve from there. If the project is not set up yet,
[TRY-IT.md](../TRY-IT.md) does that in two commands and says which Python it needs.

## Why it exists

`cost_agent` finds waste on a bill sixty days after somebody wrote it. This asks the same
question of the plan, at the moment the cost is authored, which is the only moment changing
it is free.

**It calls no model, on purpose.** The other two artifacts here route genuine judgement
through two independent raters and a blind judge. A price is arithmetic and a missing
autoscaling block is a fact about a document, so a judged dimension here would be theatre.
Knowing when not to call a model is the harder half of that argument, and a contract test
fails the build if any module in this package imports a network library.

## Run it

```bash
terraform show -json tfplan > plan.json      # needs Terraform; the fixtures below do not
.venv/bin/python -m plan_cost --plan plan.json
```

Or against the fixtures, with no Terraform, no credentials and no network. This is the
whole output, and **it exits 1 on purpose**: the plan it is judging deserves to be blocked.

```bash
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/estate/plan.json --env staging
```

```
PLAN COST  plan_cost/fixtures/estate/plan.json

  Environment      staging (from the --env flag, matching the plan)
  Monthly change   +$432.89
                   730 hours per month, rates from prices.toml, oldest row taken 2026-09-13
                   compute priced by machine type; storage attached
                   inside an instance or node pool is not included

  Priced
    google_container_node_pool.primary              +$293.46   3 x e2-standard-4, us-central1
    google_container_node_pool.spot                 +$195.64   2 x e2-standard-4 at minimum, us-central1
    google_compute_instance.bastion                  -$12.26   1 x e2-small, us-central1, removed
    google_compute_instance.legacy_runner            -$43.95   1 x n2-standard-4, us-central1 to 1 x e2-standard-4, us-central1

  Not counted
    unknown until apply    1   machine type is not known until apply
    no price row           1   google/disk/pd-balanced/us-central1
    not priceable          5   no recurring cost 1, not a cloud resource 2, usage-driven 2
    no change              1

  12 resource changes, 12 accounted for.

FINDINGS

  block   node_pool_without_autoscaling   google_container_node_pool.primary
          autoscaling absent, node_count = 3
          capacity that can never be reclaimed, which is the driver cost_agent finds on bills sixty days later

  review  no_billing_labels               google_container_node_pool.primary
          node_config.resource_labels absent
          spend that cannot be attributed to a team, which is where accountability disappears

  review  boot_disk_outlives_instance     google_compute_instance.legacy_runner
          boot_disk.auto_delete false
          the disk keeps billing after the instance is gone, which is the orphaned-storage case nobody goes looking for

DECISION  blocked

  rule fired at blocking severity   yes, node_pool_without_autoscaling
  monthly change over threshold     yes, +$432.89 over $250.00
  environment policy                staging blocks

  exit 1
```

Every other block in this README is an excerpt of a run like that one.

### Every path it has, in one sitting

[`fixtures/demo/`](fixtures/demo/README.md) holds seven plans and a synthetic rate table,
with the command and expected exit code for each:

| Demo plan | Monthly | Exit |
|---|---|---|
| `staging-over-budget.json` | +$1,222.60 | **1**, blocked |
| `staging-normal.json` | +$119.50 | 0 |
| `staging-marginal.json` | +$232.50 | 0, or **1** with `--budget-json` |
| `production-over-budget.json` | +$1,222.60 | 0, would have blocked |
| `production-normal.json` | +$270.10 | 0, over threshold but nothing fired |
| `incident-io-schedule.json` | no figure | 0 |
| `incident-io-schedule-no-environment.json` | none | **2**, refused to judge |

```bash
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/demo/staging-over-budget.json \
  --prices plan_cost/fixtures/demo/prices.demo.toml
```

Every exit code in that table is asserted in the test suite, so the demo fails the build
rather than failing in front of an audience.

## Use it in CI

Exit codes follow one contract, shared by everything runnable here and written down in
[`ci/__init__.py`](../ci/__init__.py):

```
0  OK         ran, judged, nothing to stop for
1  BLOCKED    ran, judged, and the answer is stop
2  UNJUDGED   could not judge; this never means clean
```

**2 is the one that matters.** A bad input, an unreadable file or a format nobody has checked
lands there rather than on 0, because a pipeline that reads "I could not tell" as "fine" is
worse than no check. A shell step fails on both 1 and 2, which is what you want: a gate that
could not run is not a gate that passed.

**It is a gate.** All three codes are reachable:

```yaml
- name: Price the plan before it merges
  run: |
    terraform show -json tfplan > plan.json
    python -m plan_cost --plan plan.json --env staging
```

Staging blocks and production reports, so the same step is safe to add to both pipelines
without standing in front of an urgent production change. Point `--budget-json` at a budget
your organisation already owns and the threshold comes from there instead of the policy file.

The repository runs these against its own fixtures on every push, in the `gates` job of
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml), asserting each exit code with
[`tools/expect-exit.sh`](../tools/expect-exit.sh). Until that job existed this was a CI gate
that had never run in CI.

The contract itself is covered by `tests/unit/test_ci_contract.py` and
`tests/integration/test_unreadable_input.py`, 18 tests that assert every tool answers
input it cannot read with 2 and a message rather than a traceback.

## How it works

**Every resource is accounted for.** Twelve changed, twelve placed. A cost check that prices four resources out of
twelve and prints one total has produced a confident wrong answer, and a reader cannot tell
it apart from a correct one. So every changed resource lands in exactly one bucket, and the
buckets are asserted to sum to the number of changes in code, not only in a test:

| Bucket | Meaning |
|---|---|
| priced | the plan fixes its recurring cost and the table has a rate |
| unknown until apply | a priced type whose machine type or size is not decided yet |
| no price row | a priced type with known attributes and no rate in the table |
| not priceable | usage-driven, no recurring cost, or not a cloud resource at all |
| no change | a no-op or a read |

Nothing is ever priced at zero to make a total tidy. Point it at a plan of SaaS resources
and it says so rather than implying a large change is free:

```bash
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/saas/plan.json --env staging
```

```
  Monthly change   nothing here can be priced

  Not counted
    not priceable          5   not a cloud resource 5

  5 resource changes, 5 accounted for.
```

**The gate blocks in staging and reports in production.** It blocks only when all three
hold: a rule fired at a blocking severity, the monthly change is over the threshold, and
this environment blocks. Staging blocking while production reports is the opposite of the
obvious arrangement and it is deliberate. Gate where a fix is still cheap. A cost tool
standing in front of an urgent production change does more harm than the change it is
objecting to, so there it reports, says what it would have done, and stands aside.

The same plan as above, judged as production:

```bash
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/estate/plan.json --env production
```

```
DECISION  reported, would have blocked in staging

  rule fired at blocking severity   yes, node_pool_without_autoscaling
  monthly change over threshold     yes, +$432.89 over $250.00
  environment policy                production reports

  exit 0
```

Exit 0 when it does not block, 1 when it does, and 2 when it could not judge at all: an
unreadable plan, a format version nobody has checked, a price table contradicting itself,
or no environment from either source. **Exit 2 never means expensive.** The environment
comes from the plan's own `variables.environment`, with `--env` as a fallback and an
override, and a missing environment is an error rather than a default, because a gate that
quietly became a report is worse than no gate.

**Three rules, each about a cost consequence visible in the document:**

| Rule | What it catches |
|---|---|
| `node_pool_without_autoscaling` | capacity that can never be reclaimed, which is the driver `cost_agent` finds on bills sixty days later |
| `no_billing_labels` | spend that cannot be attributed to a team, which is where accountability disappears |
| `boot_disk_outlives_instance` | a disk that keeps billing after its instance is gone |

Two restraints matter as much as the rules. Nothing fires on an attribute the plan does not
know yet, and nothing fires on a resource being deleted, because a finding about something
going away is advice nobody can take.

The labels rule is the one worth reading the provider documentation for. A node pool
carries two label attributes, and `node_config.labels` are Kubernetes labels that never
reach a bill. The ones that do are `node_config.resource_labels`. A rule written against
the obvious attribute would have stayed silent on unattributed spend and fired on
infrastructure that was labelled correctly.

Findings quote the attribute they fired on, and findings go into build logs, so a value the
plan marks sensitive is named but never printed.

### Adding a resource type, or a second cloud

Three places, and the registry is deliberately a module rather than a dictionary buried in
the pricing code, so the seam is visible:

1. [`registry.py`](registry.py): how to read the priced shape out of that resource type's
   attributes, and which attribute carries its billing labels.
2. [`prices.toml`](prices.toml): one row per priced unit and region, each with a source and
   a date, plus a mapping entry if a catalogue SKU can refresh it.
3. [`rules.py`](rules.py): only if the type needs a rule of its own.

Price keys carry their provider (`google/machine-type/e2-standard-4/us-central1`), so AWS
rows sit beside these without colliding.

## What you can argue with

```bash
cat plan_cost/policy.toml
cat plan_cost/prices.toml
```

**`policy.toml` holds what blocks and where**: rule severities, the monthly threshold, the
staleness age, and which environments block rather than report. Only
`node_pool_without_autoscaling` blocks by default, because stopping a build over a missing
label teaches people to work around the gate. Changing any of that is a config edit.

**`prices.toml` holds every figure**, each row carrying its source URL and the date it was
read, so any number can be checked without leaving the repository. Amounts are strings
parsed to exact decimals, because a float total invites a rounding argument that has
nothing to do with the analysis. These are third-party list prices, not your rates: nobody
with a committed use discount pays them, and replacing the file with your own rate card
changes nothing else.

**No disk price ships.** The source that publishes machine prices per region publishes disk
prices only as an average across regions, and these keys are regional, so writing that
average into a `us-central1` row would be an invented number wearing a citation. Disks
report as having no price row instead. That gap closes from Google's own catalogue rather
than by hand:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus" > skus.json

# --refresh-prices rewrites the committed table in place. Try it on a copy first:
cp plan_cost/prices.toml /tmp/prices.toml
.venv/bin/python -m plan_cost --refresh-prices skus.json --prices /tmp/prices.toml
diff plan_cost/prices.toml /tmp/prices.toml
```

No credentials to hand? The same thing runs against the recorded response:

```bash
cp plan_cost/prices.toml /tmp/prices.toml
.venv/bin/python -m plan_cost --refresh-prices plan_cost/fixtures/catalogue/skus.json \
  --prices /tmp/prices.toml
```

```
PRICE REFRESH  /tmp/prices.toml

  added           google/disk/pd-balanced/us-central1
  added           google/disk/pd-ssd/us-central1
  no mapping      google/machine-type/e2-standard-4/us-central1, left exactly as it was
  no mapping      google/machine-type/e2-small/us-central1, left exactly as it was
  no mapping      google/machine-type/n2-standard-4/us-central1, left exactly as it was
```

Rows it cannot refresh are named and left byte-identical, rather than coming out of a
refresh looking fresh. Machine types are all of them today: Compute Engine prices cores and
memory as separate SKUs, so no single SKU equals an `e2-standard-4`. A SKU priced in tiers
is refused for the same reason. If your access token has expired, Google returns an error
body rather than a catalogue, and the refresh exits 2 saying so rather than reporting that
nothing matched.

**The threshold can come from your own budget** rather than from a number somebody typed:

```bash
gcloud billing budgets list --billing-account=YOUR-BILLING-ACCOUNT-ID --format=json > budgets.json
.venv/bin/python -m plan_cost --plan plan.json --budget-json budgets.json --budget-name platform-monthly
```

That path is verifiable offline too, against a recorded response:

```bash
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/estate/plan.json --env staging \
  --budget-json plan_cost/fixtures/budget/budgets.json --budget-name platform-monthly
```

```
  monthly change over threshold     yes, +$432.89 over $200.00
                                    budget "platform-monthly": $800.00 x 25% = $200.00. Current spend is
                                    unknown to this tool, so this judges the change on its own. It covers
                                    projects/123456789012; calendar period MONTH, which was not matched
                                    against this plan
```

The budget API has no per-change threshold, so the tool derives one: the amount times the
lowest threshold percentage, which is the line the organisation itself chose to be told
about. It shows that arithmetic so you can draw the line somewhere else, prints the
budget's filter so you can see what it covers, and states plainly that it does not know
current spend.

Two budgets and no name is an error, exit 2, and so is naming a budget the response does
not hold. Neither falls back. If it fell back to the policy file it would judge the plan
against a threshold nobody asked for, and in these fixtures that threshold is the looser
of the two, so the gate would have quietly relaxed at the moment somebody tightened it.
A budget that is correctly identified but cannot yield a threshold, one carrying
`lastPeriodAmount` and no rules, does still warn and fall back: that is a fact about the
data rather than a mistake in the request.

## The paid path

**There isn't one, and that is the point.** This artifact spends nothing, ever. Both API
paths above read files you saved with documented commands, so CI needs no credential and
nothing here opens a socket.

## What it does not do

- **No live billing call has ever been made from this code.** Catalogue and budget
  responses arrive as files you saved. Every path here was tested against recorded
  responses, and the API shapes come from the current documentation, but nothing has run
  against a live billing account.
- **The fixtures are hand-authored** against Terraform's documented JSON format. No
  `terraform` binary was run, because none is installed where this was built.
- **Compute is priced by machine type.** Storage attached inside an instance or a node pool
  is not in its figure, and the report says so on every run that prices a monthly change. A
  plan where nothing could be priced carries no figure, so it carries no caveat either. A
  disk that appears as its own resource is priced as one.
- **It judges one change in isolation.** Current spend needs the billing export, which is a
  different data source.
- **Google Cloud only.** A second cloud is an extension point, not a claim.
- **Built in a day.** Not production-tested.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_plan_parse.py tests/unit/test_plan_registry.py \
  tests/unit/test_plan_coverage.py tests/unit/test_plan_prices.py tests/unit/test_plan_pricing.py \
  tests/unit/test_plan_rules.py tests/unit/test_plan_policy.py tests/unit/test_plan_gate.py \
  tests/unit/test_plan_refresh.py tests/unit/test_plan_budget.py \
  tests/unit/test_plan_budget_ambiguity.py tests/unit/test_plan_gcp.py \
  tests/integration/test_plan_cost_cli.py tests/integration/test_plan_cost_demo.py \
  tests/contract/test_no_network.py
```

162 tests, offline, no credentials.

## Dependencies

Standard library only. `tomllib` reads the two config files and `json` reads plans, and the
price table is written back by a small emitter rather than a TOML writer dependency. This
package imports nothing from `ensemble`, `ledger` or either agent, and it imports no
network library at all, which `tests/contract/test_no_network.py` enforces.
