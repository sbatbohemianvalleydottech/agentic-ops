# cost_agent

Finds the structural reasons a cloud bill is what it is, rather than ranking line
items by size.

**Run every command here from the repository root.** If you have not set the project up
yet, [TRY-IT.md](../TRY-IT.md) does that in two commands and says which Python it needs.

## Why it exists

**A line item**: "`a-node-1` costs $240,901 a year and runs at 38% utilisation." That is a
number off a bill. Anyone with billing access can read it out.

**A structural driver**: "Nothing in this estate scales with demand. Eight resources
across compute, database, cache and CI are provisioned for peak and none autoscale.
That is 78.6% of the bill, and it is one absent management practice rather than eight
engineering problems."

Both figures come from the `estate_a` fixture below, and neither needs the tool to check:

```bash
grep a-node-1 cost_agent/fixtures/estate_a/costs.csv                        # 19800.00 a month
grep -A1 '"a-node-1"' cost_agent/fixtures/estate_a/inventory.json | tail -1  # utilisation_avg
```

$19,800.00 a month times the 12.1667 annualisation multiplier the report prints on every
run is $240,900.66, which is the $240,901 above, and `utilisation_avg` is 0.38. The report
itself aggregates by driver and never prints a per-resource total, so those two commands
are the way to check it. The second figure is the one worth building a tool for, so a driver must explain more than one
resource and name what is *missing* rather than what is expensive. Single-resource drivers
are still reported, but flagged, because a driver that explains one line is a line item
wearing a better name.

## Run it

```bash
.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json \
  --as-of 2026-09-01
```

Offline, deterministic, no credentials, exit 0. That is deliberate: the arithmetic a
sceptical reader will attack should be reproducible by them without an account.

Now run the second estate, which is the check that matters:

```bash
.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_b/costs.csv \
  --inventory cost_agent/fixtures/estate_b/inventory.json \
  --as-of 2026-09-01
```

| | Estate A | Estate B |
|---|---|---|
| Dominant driver | Capacity management, 78.6% | Commercial, 67.5% |
| Shape | Provisioned for peak, never revisited | Well-sized, uncommitted, untagged, littered with detached volumes |

Same code, different disease. If both produced the same drivers, the tool would have
learned its test data.

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

**It is a reporter, not a gate.** It returns 0 or 2 and never 1. An estate costing money is
not a build-breaking condition, and inventing a dollar threshold so it could return 1 would be
dressing up an analysis as a gate:

```yaml
- name: Publish the cost driver analysis
  run: |
    python -m cost_agent --costs costs.csv --inventory inventory.json \
      --as-of "$(date -I)" | tee analysis.txt
```

A schedule suits it better than a merge gate. The thing worth failing a build over is the
change that creates the waste, and that is `plan_cost`.

The repository runs these against its own fixtures on every push, in the `gates` job of
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml), asserting each exit code with
[`tools/expect-exit.sh`](../tools/expect-exit.sh). Until that job existed this was a CI gate
that had never run in CI.

The contract itself is covered by `tests/unit/test_ci_contract.py` and
`tests/integration/test_unreadable_input.py`, 18 tests that assert every tool answers
input it cannot read with 2 and a message rather than a traceback.

## How it works

**Attribution is single-owner, and the rule is printed so you can argue with the rule.**
A legacy cluster is both badly capacity-managed and something that should not exist. Both
are true. The tool assigns it to one and records what it chose between.

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

**Drivers cannot sum to more than the bill.** Each resource's cost is attributed to
exactly one driver, and a test asserts the totals exactly rather than within a tolerance.
Money is `Decimal` end to end, because summing a few thousand floats can drift past a
total by cents, and a reader who spots 100.0001% has a reason to distrust everything else.

**No rule branches on a service name.** A test asserts the same resource shape classifies
identically when the service is renamed to something nobody has heard of. Both of those
tests are in the command under [Run its tests](#run-its-tests), so the claims are checkable
rather than asserted.

**Savings are ranges, and every driver carries a question.** The tool sees utilisation. It
cannot see contracts, reserved capacity, a workload that looks idle because it is a warm
standby, or a compliance hold on a bucket. A point estimate would claim knowledge it does
not have, so each driver reports a range with a conservative lower bound plus the single
question that would confirm it. That question is where the analysis stops and a human takes over.

**Nothing is silently dropped.** Every resource from either input ends up somewhere:
attributed to a driver, listed as contested, reported as unassessable, flagged as
unmatched, or counted as healthy. A resource priced but not inventoried, and one
inventoried but not priced, are both findings rather than noise. Missing utilisation makes
a resource unassessable, never healthy: you cannot call something well-sized on absent
evidence. **Every category prints whether or not anything is in it**, an empty one saying
`none`, because an absent heading and "checked, found nothing" are different claims and a
reader cannot tell them apart. Run both estates and compare: estate_a has nothing healthy,
estate_b has nothing unassessable and nothing unmatched, and all four headings appear in
both.

**Retirement is a stated commitment, never an inference.** The inventory takes an optional
`decommission_at` per resource, because the tool does not get to decide which of your
platforms are obsolete.

It matters more than it looks. An earlier version filed a platform with a published
end-of-life date under *capacity management*, because utilisation was the only signal it
had for "should this exist". Filed as capacity its recoverable fraction is 0.30; filed as
elimination it is 1.00, so on a large estate the same evidence produced answers millions
apart. Worse, it would have told a migration team to go and right-size a cluster they had
already committed to deleting.

Anything scheduled now reports its horizon beside the savings range, because "eliminable"
and "eliminable by a date three years out" are different claims and only the second is
true. A date already in the past is reported separately: still paying for something that
should already be gone is a stronger finding than a planned retirement.

## What you can argue with

```bash
cat cost_agent/thresholds.toml
```

What counts as "under-utilised" is the substance of the analysis, not an implementation
detail. Every arguable number lives in that file with the reasoning beside it, so a
reviewer can disagree with it directly instead of taking the findings on faith. Disagree in
a copy and re-run, with no code change:

```bash
cp cost_agent/thresholds.toml /tmp/mine.toml
# edit /tmp/mine.toml, then:
.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json \
  --as-of 2026-09-01 --thresholds /tmp/mine.toml
```

The attribution order above is the other arguable thing. If you think a commitment should
beat right-sizing, that is a real position, and it changes which driver owns the dollars.

## The paid path

Needs `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`, and the provider library, which the default
install does not include:

```bash
uv pip install -e ".[dev,providers]"
cp .env.example .env    # paste both keys, or export them; an export always wins

.venv/bin/python -m cost_agent \
  --costs cost_agent/fixtures/estate_a/costs.csv \
  --inventory cost_agent/fixtures/estate_a/inventory.json \
  --as-of 2026-09-01 --confidence
```

Without those keys it stops immediately and says which one is missing, rather than failing
part way through a paid run.

It rates each driver through [`ensemble`](../ensemble/README.md): two independent assessors
from different providers, plus a judge that never learns whether they agreed. A split marks
the driver `NEEDS_REVIEW` rather than settling on "medium", because an averaged confidence
is a fabricated agreement wearing a number.

Every model is probed with one minimal call first, and the run stops there if any of them
fails, so a dead model or an unfunded account costs about $0.0003 to find rather than a
full run. This tool has no probe-only flag, but both agents read the same model settings,
so [`rca_agent --check`](../rca_agent/README.md#the-paid-path) probes exactly the models
this would use. Progress goes to stderr with a running cost; the report stays on stdout.
The report names the two assessors and the judge, because what produced a rating is the
first thing an audit asks, and spend lands in `.ledger/calls.jsonl`.

## What it does not do

- **It cannot see contracts, commitments or intent.** Everything it knows arrives in the
  two input files, which is why savings are ranges and every driver carries a question.
- **It does not decide what should be retired.** `decommission_at` is something you state.
- **The fixtures are synthetic**, and every figure in this README comes from them or from
  the modelled estate described above. No real billing data is in this repository.
- **Built in a week.** Not production-tested, and it has never run against a live billing
  export.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_classify.py tests/unit/test_drivers.py \
  tests/unit/test_savings.py tests/unit/test_inputs.py tests/unit/test_thresholds.py \
  tests/unit/test_cost_report.py tests/integration/test_generalises.py \
  tests/integration/test_confidence.py tests/integration/test_cost_report_consistency.py
```

88 tests, offline, no credentials.

## Dependencies

Standard library only, plus `ensemble` and `ledger` from this repository. Thresholds are
TOML read with `tomllib`. The optional confidence pass needs `litellm`, which arrives with
the `providers` extra and not with the default `dev` install. Check with
`uv pip show litellm`.
