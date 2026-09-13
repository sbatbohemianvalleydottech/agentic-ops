# plan_cost

Prices a Terraform plan before it merges, and blocks in staging, where a fix is still cheap.

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
terraform show -json tfplan > plan.json
.venv/bin/python -m plan_cost --plan plan.json
```

Or against the fixtures, with no Terraform, no credentials and no network:

```bash
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/estate/plan.json --env staging
```

```
PLAN COST  plan_cost/fixtures/estate/plan.json

  Environment      staging (from the --env flag, matching the plan)
  Monthly change   +$432.89
                   730 hours per month, list prices, oldest row taken 2026-09-13
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
```

## Every resource is accounted for

Twelve changed, twelve placed. That line is the point of the tool. A cost check that prices
four resources out of twelve and prints one total has produced a confident wrong answer,
which is the failure this repository exists to catch, and a reader cannot tell it apart from
a correct one.

So every changed resource lands in exactly one bucket, and the buckets are asserted to sum
to the number of changes in code, not only in a test:

| Bucket | Meaning |
|---|---|
| priced | the plan fixes its recurring cost and the table has a rate |
| unknown until apply | a priced type whose machine type or size is not decided yet |
| no price row | a priced type with known attributes and no rate in the table |
| not priceable | usage-driven, no recurring cost, or not a cloud resource at all |
| no change | a no-op or a read |

Nothing is ever priced at zero to make a total tidy. Point it at a plan of SaaS resources
and it says so rather than implying a large change is free:

```
.venv/bin/python -m plan_cost --plan plan_cost/fixtures/saas/plan.json --env staging

  Monthly change   nothing here can be priced

  Not counted
    not priceable          5   not a cloud resource 5

  5 resource changes, 5 accounted for.
```

## The gate: staging blocks, production reports

It blocks only when all three hold: a rule fired at a blocking severity, the monthly change
is over the threshold, and this environment blocks.

Staging blocks and production reports. That is the opposite of the obvious arrangement and
it is deliberate. Gate where a fix is still cheap. A cost tool standing in front of an
urgent production change does more harm than the change it is objecting to, so there it
reports, says what it would have done, and stands aside.

```
DECISION  reported, would have blocked in staging

  rule fired at blocking severity   yes, node_pool_without_autoscaling
  monthly change over threshold     yes, +$432.89 over $250.00
  environment policy                production reports

  exit 0
```

Exit 0 when it does not block, 1 when it does, and 2 when it could not judge at all: an
unreadable plan, a format version nobody has checked, a price table contradicting itself, or
no environment from either source. Exit 2 never means expensive. The environment comes from
the plan's own `variables.environment`, with `--env` as a fallback and an override, and a
missing environment is an error rather than a default, because a gate that quietly became a
report is worse than no gate.

## The three rules

| Rule | What it catches |
|---|---|
| `node_pool_without_autoscaling` | capacity that can never be reclaimed, which is the driver `cost_agent` finds on bills later |
| `no_billing_labels` | spend that cannot be attributed to a team, which is where accountability disappears |
| `boot_disk_outlives_instance` | a disk that keeps billing after its instance is gone |

Severities live in [`policy.toml`](policy.toml) beside the threshold, so what blocks is a
config edit rather than a code change. Only the first blocks by default: stopping a build
over a missing label teaches people to work around the gate.

Two restraints matter as much as the rules. Nothing fires on an attribute the plan does not
know yet, and nothing fires on a resource being deleted, because a finding about something
going away is advice nobody can take.

The labels rule is the one worth reading the provider documentation for. A node pool carries
two label attributes, and `node_config.labels` are Kubernetes labels that never reach a bill.
The ones that do are `node_config.resource_labels`. A rule written against the obvious
attribute would have stayed silent on unattributed spend and fired on infrastructure that was
labelled correctly.

Findings quote the attribute they fired on, and findings go into build logs, so a value the
plan marks sensitive is named but never printed.

## Prices you can check

Every row in [`prices.toml`](prices.toml) carries its source URL and the date it was read,
so any figure can be checked without leaving the repository. Amounts are strings parsed to
exact decimals, because a float total invites a rounding argument that has nothing to do
with the analysis.

**These are third-party list prices, not your rates.** Nobody with a committed use discount
pays them. Replace the file with your own rate card and nothing else changes, because no
code reads a price from anywhere else.

**No disk price ships.** The source that publishes machine prices per region publishes disk
prices only as an average across regions, and these keys are regional, so writing that
average into a `us-central1` row would be an invented number wearing a citation. Disks report
as having no price row instead, which the estate fixture shows on purpose.

That gap closes with one command, from Google's own catalogue rather than by hand:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus" > skus.json

.venv/bin/python -m plan_cost --refresh-prices skus.json
```

```
PRICE REFRESH  plan_cost/prices.toml

  added           google/disk/pd-balanced/us-central1
  added           google/disk/pd-ssd/us-central1
  no mapping      google/machine-type/e2-standard-4/us-central1, left exactly as it was
  no mapping      google/machine-type/e2-small/us-central1, left exactly as it was
  no mapping      google/machine-type/n2-standard-4/us-central1, left exactly as it was
```

Rows it cannot refresh are named and left byte-identical, rather than coming out of a
refresh looking fresh. Machine types are all of them today: Compute Engine prices cores and
memory as separate SKUs, so no single SKU equals an `e2-standard-4`. A SKU priced in tiers is
refused for the same reason, because picking one of those tiers would be a choice the table
could not show.

## The threshold from your own budget

Rather than a number somebody typed into a config file, the limit can come from the budget
the organisation already set:

```bash
gcloud billing budgets list --billing-account=0X0X0X-0X0X0X-0X0X0X --format=json > budgets.json
.venv/bin/python -m plan_cost --plan plan.json --budget-json budgets.json --budget-name platform-monthly
```

```
  monthly change over threshold     yes, +$432.89 over $200.00
                                    budget "platform-monthly": $800.00 x 25% = $200.00.
                                    Current spend is unknown to this tool, so this judges
                                    the change on its own. It covers projects/123456789012;
                                    calendar period MONTH, which was not matched against
                                    this plan
```

The budget API has no per-change threshold, so the tool derives one: the amount times the
lowest threshold percentage, which is the line the organisation itself chose to be told
about. It shows that arithmetic so you can draw the line somewhere else, prints the budget's
filter so you can see what it covers, and states plainly that it does not know current
spend. Two budgets and no name is an error rather than a pick.

## What it does not do

- **No live billing call has ever been made from this code.** Catalogue and budget responses
  arrive as files you saved with the commands above. Every path here was tested against
  recorded responses, and the API shapes come from the current documentation, but nothing has
  run against a live billing account.
- **The fixtures are hand-authored** against Terraform's documented JSON format. No
  `terraform` binary was run, because none is installed where this was built.
- **Compute is priced by machine type.** Storage attached inside an instance or a node pool
  is not in its figure, and the report says so on every run. A disk that appears as its own
  resource is priced as one.
- **It judges one change in isolation.** Current spend needs the billing export, which is a
  different data source.
- **Google Cloud only.** A second cloud is an extension point, not a claim.
- **Built in a day, for a project.** Not production-tested.

## Adding a resource type, or a second cloud

Three places, and the registry is deliberately a module rather than a dictionary buried in
the pricing code, so the seam is visible:

1. [`registry.py`](registry.py): how to read the priced shape out of that resource type's
   attributes, and which attribute carries its billing labels.
2. [`prices.toml`](prices.toml): one row per priced unit and region, each with a source and
   a date, plus a mapping entry if a catalogue SKU can refresh it.
3. [`rules.py`](rules.py): only if the type needs a rule of its own.

Price keys carry their provider (`google/machine-type/e2-standard-4/us-central1`), so AWS
rows sit beside these without colliding.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_plan_parse.py tests/unit/test_plan_registry.py \
  tests/unit/test_plan_coverage.py tests/unit/test_plan_prices.py tests/unit/test_plan_pricing.py \
  tests/unit/test_plan_rules.py tests/unit/test_plan_policy.py tests/unit/test_plan_gate.py \
  tests/unit/test_plan_refresh.py tests/unit/test_plan_budget.py \
  tests/integration/test_plan_cost_cli.py tests/contract/test_no_network.py
```

125 tests, offline, no credentials. The design and the evidence behind it are in
[specs/011-plan-cost](../specs/011-plan-cost/).
