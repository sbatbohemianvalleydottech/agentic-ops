# cost_agent

Finds the structural reasons a cloud bill is what it is, rather than ranking line
items by size.

## The distinction it exists for

**A line item**: "Kubernetes costs $240,901 a year and runs at 38% CPU." That is a number
off a bill. Anyone with billing access can read it out.

**A structural driver**: "Nothing in this estate scales with demand. Eight resources
across compute, database, cache and CI are provisioned for peak and none autoscale.
That is 78.6% of the bill, and it is one absent management practice rather than eight
engineering problems."

The second is worth building a tool for. So a driver must explain more than one resource
and name what is *missing*, not what is expensive. Single-resource drivers still get
reported, but flagged, because a driver that explains one line is a line item wearing a
better name.

## Run it

```bash
uv venv && uv pip install -e ".[dev]"

.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json \
  --as-of 2026-09-01
```

Offline, deterministic, no credentials. That is deliberate: the arithmetic a sceptical
reader will attack should be reproducible by them without an account.

## The two things a reviewer should attack first, and the answers

**"Your drivers sum to more than the bill."** They cannot. Each resource's cost is
attributed to exactly one driver, and a test asserts the totals exactly rather than
within a tolerance. Money is `Decimal` end to end, because summing a few thousand floats
can drift past a total by cents and a reader who spots 100.0001% has a reason to distrust
everything else.

**"You just hardcoded the answer for your fixture."** No rule branches on service name,
cloud, or any product name. A test asserts the same resource shape classifies identically
when the service is renamed to something nobody has heard of. And the two fixture estates
produce genuinely different diagnoses:

| | Estate A | Estate B |
|---|---|---|
| Dominant driver | Capacity management, 78.6% | Commercial, 67.5% |
| Shape | Provisioned for peak, never revisited | Well-sized, uncommitted, untagged, littered with detached volumes |

Same code, different disease. If both produced the same drivers, the tool would have
learned its test data.

## Attribution: the rule, so you can argue with the rule

A legacy cluster is both badly capacity-managed and something that should not exist.
Both are true. The tool assigns it to one and records what it chose between.

```
1. Workload elimination   this should not exist at all
2. Retention lifecycle    this data should not still be here
3. Capacity management    this should exist, at a different size
4. Commercial             this should exist at this size, on better terms
```

Ordered by whether fixing one makes the others moot. There is no point right-sizing a
cluster you are about to delete, or buying a commitment for capacity you are about to
halve. Each remedy subsumes the ones below it, so the highest match owns the dollars and
the alternative is printed in the contested section.

## The thresholds are the argument

```bash
cat cost_agent/thresholds.toml
```

What counts as "under-utilised" is the substance of the analysis, not an implementation
detail. Every arguable number lives in that file with the reasoning next to it, so a
reviewer can disagree with it directly instead of taking the findings on faith.

```bash
.venv/bin/python -m cost_agent --costs ... --inventory ... --thresholds mine.toml
```

## Savings are ranges, and every driver carries a question

The tool sees utilisation. It cannot see contracts, reserved capacity, a workload that
looks idle because it is a warm standby, or a compliance hold on a bucket. A point
estimate would claim knowledge it does not have.

So each driver reports a range with a conservative lower bound, plus the single question
that would confirm it. That question is where the analysis honestly stops, and it is the
most credible thing in the output.

## Confidence, optional

```bash
export ANTHROPIC_API_KEY=... GEMINI_API_KEY=...
.venv/bin/python -m cost_agent --costs ... --inventory ... --confidence
```

Rates each driver through [`ensemble`](../ensemble/README.md): two independent assessors
from different providers, plus a judge that never learns whether they agreed. A split
marks the driver `NEEDS_REVIEW` rather than settling on "medium", because an averaged
confidence is a fabricated agreement wearing a number.

Spend lands in `.ledger/calls.jsonl`.

## Nothing is silently dropped

Every resource from either input ends up somewhere: attributed to a driver, listed as
contested, reported as unassessable, flagged as unmatched, or counted as healthy. A
resource priced but not inventoried, and one inventoried but not priced, are both
findings rather than noise. Missing utilisation makes a resource unassessable, never
healthy: you cannot call something well-sized on absent evidence.

## Dependencies

Standard library only, plus `ensemble` and `ledger` from this repository. Thresholds are
TOML read with `tomllib`. The optional confidence pass needs `litellm`, installed with
`pip install -e ".[providers]"`.
