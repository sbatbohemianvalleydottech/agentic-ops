# rca_agent

Catches the incident review that reads well and says nothing. An RCA here is a root cause
analysis: the write-up a team produces after an incident.

**Run every command here from the repository root**, one level above this folder, because
`.venv` and the fixtures resolve from there. If the project is not set up yet,
[TRY-IT.md](../TRY-IT.md) does that in two commands and says which Python it needs.

## Why it exists

A fluent RCA looks like a good one right up until the same incident recurs. Every failure
below is invisible to someone skimming for prose quality, and every one means the
organisation learned nothing:

- The cause is "human error", when the person was the last line of a system that had
  already failed them.
- The description slides into what *should* have happened, so nobody ever establishes
  what did.
- The action items are "add more monitoring" and "be more careful", neither of which is a
  thing anyone can be assigned.
- Six action items were agreed. Ninety days later five are open and nobody noticed.

## Run it

```bash
.venv/bin/python -m rca_agent \
  --corpus rca_agent/fixtures/corpus \
  --as-of 2026-09-01 --completion
```

Offline and instant, exit 0. These are the checks worth running *before* a debrief is
scheduled, so they cost nothing and wait for nothing.

That one command prints 77 lines: a block per review for all eight fixtures, each
with its defects quoted from the document, and then the completion summary across the
corpus. Every quoted block in this README is a slice of that output.

**Keep `--as-of`.** It defaults to today, and ages are measured from it, so dropping it
changes the numbers: the median age of open items reads 163 days at `2026-09-01` and 175
days if you omit the flag. That is a parameter so a run reproduces exactly, not a
formality.

The last section of the output is the figure no single review surfaces:

```
ACTION ITEM COMPLETION

  Items:                    21
  Closed:                   13 (62%)
  Median age of open items: 163 days
  Closed with no evidence:  1

  Export policy breaches
    Follow-ups not in a tracker beyond the window after closure.
    - rca-abandoned

  Repeated action items
    The same commitment made in more than one review, which is evidence
    the first attempt never landed.
    - "Post the incident summary to the status page"
    - "Set a default lock timeout of 5s on all migrations"
```

Closed-with-evidence and closed-without are counted separately, because they are different
claims wearing the same word, and collapsing them lets a team close an item by editing a
field. A repeated action item is the interesting one: the same commitment appearing in two
reviews is evidence the first attempt never landed.

### Point it at your own reviews

`--corpus` takes any directory of JSON files in this shape, and
[`fixtures/corpus/rca-good.json`](fixtures/corpus/rca-good.json) is the template:

```json
{
  "rca_id": "rca-good",
  "severity": "sev1",
  "timeline": [{"name": "detection", "at": "2026-03-01T09:12:00"}],
  "impact": "412 merchants saw checkout errors for 78 minutes.",
  "stated_cause": "...",
  "contributing_factors": ["..."],
  "narrative": "...",
  "participants": ["Rae Lindqvist", "Sam Okafor"],
  "action_items": [{
    "title": "Set a default lock timeout of 5s on all migrations",
    "state": "closed",
    "created": "2026-03-02T00:00:00",
    "owner": "Rae Lindqvist",
    "due": "2026-04-01T00:00:00",
    "tracker_ref": "PLAT-2211",
    "category": "prevent",
    "closure_evidence": "PR 4412"
  }],
  "closed_at": "2026-03-05T00:00:00",
  "followups_exported_at": "2026-03-06T00:00:00"
}
```

Which timeline moments are required, and the window follow-ups must be exported in, are
config rather than code. See [What you can argue with](#what-you-can-argue-with).

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

**It reports by default and gates when asked.** Structural defects are objective and free to
check, so a review missing a detection timestamp should not close:

```yaml
- name: Block a review with structural defects
  run: python -m rca_agent --corpus reviews/ --fail-on-defects
```

Without `--fail-on-defects` it prints the same report and returns 0. Gating is opt-in because
a tool that starts failing builds the day somebody upgrades it is a tool people pin and
forget. The judgement pass is not wired in here on purpose: it costs money per review and
belongs on a schedule or a label, not on every push.

The repository runs these against its own fixtures on every push, in the `gates` job of
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml), asserting each exit code with
[`tools/expect-exit.sh`](../tools/expect-exit.sh). Until that job existed this was a CI gate
that had never run in CI.

The contract itself is covered by `tests/unit/test_ci_contract.py` and
`tests/integration/test_unreadable_input.py`, 18 tests that assert every tool answers
input it cannot read with 2 and a message rather than a traceback.

## How it works

**Two layers, and the split is the design.**

*Structural, deterministic, free.* Timeline completeness and ordering. Impact quantified.
Blame language. Action items with an owner, a due date, a tracker reference and a category.
At least one item that actually prevents recurrence. An RCA missing a detection timestamp
does not need a second opinion, and paying for one would be the tool failing to think.

*Judgement, gated, costs money.* Does the cause stop at the trigger. Is what happened kept
separate from what should have happened. Would the preventive items actually prevent
anything. Each dimension is assessed by two independent models plus a judge, through
[`ensemble`](../ensemble/README.md).

**Blame is detected from language, not names.**

> "Sam restarted the service" is good practice.
> "Sam failed to check the config" is the failure.

So the check reads a configurable phrase list plus the incident's own participant roster,
over `stated_cause` and `contributing_factors` **only, never the narrative.**
Named-entity recognition over the whole document would flag every timeline entry recording
who did what, which is exactly the blameless detail a good RCA should contain. A check that
misfires there trains people to ignore it, and then it catches nothing at all. There is a
test that puts *"Sam Okafor failed to check the config. Human error throughout."* in the
narrative and asserts no defect is raised.

**What the eight fixtures are for.** Four break exactly one structural check:
`rca-blame`, `rca-broken-timeline`, `rca-detection-only` and `rca-vague-impact`.
`rca-no-tickets` breaks two at once, because action items with no owner or tracker are
usually also not preventive. Three break none at all:

| Fixture | Structural result | Why it is in the corpus |
|---|---|---|
| `rca-good` | clean | the control. If this ever fails, a check has become too strict |
| `rca-abandoned` | clean | its failure is in the completion report, not the document: follow-ups never reached a tracker |
| `rca-hollow` | clean | it passes everything and explains nothing |

`rca-hollow` is the one that matters:

```
RCA rca-hollow

  No structural defects.
```

Its stated cause is "A bad deploy went out and caused elevated latency across the API
tier." Four ordered timeline moments. Impact quantified to the user and the minute.
Blameless language. A declared preventive action item. Follow-ups exported on time. It
passes everything, and it explains nothing, because the cause it gives is the trigger.

That fixture is the entire justification for the judgement layer. If it also failed a
structural check, the deterministic layer would catch it first and the models would be
proving something already proven.

**Judgement dimensions are gated one at a time**, not as one overall grade. A single grade
tells a reviewer nothing about *what to look at*, and one contested judgement would halt
the whole review. From a live run on `rca-hollow`, with each rater's reasoning left out:

```
    cause_not_trigger: weak
    no_alternate_reality: CONTESTED, needs human review
      Assessment halted. Assessors disagreed: ...
    actions_would_prevent: weak
```

A contested dimension gets **no grade at all**. "Adequate", sitting between one assessor's
"weak" and another's "strong", is a number nobody argued for.

### A dimension that always halts is a defect, not a result

`no_alternate_reality` contested in every run in every context, fixtures and published
incident reports alike, while costing 1.7 to 2.0 times the dimensions that reached a grade.
Two assessors disagreeing is the gate working. Two assessors *always* disagreeing is a
question that cannot be answered from what they are given.

Two faults sat in one sentence. It asked whether the review "keeps the description of what
actually happened separate from what should have happened", and **an assessor never sees the
review as a document**: it sees an evidence bundle whose records are already labelled and
already separated, `Stated cause:`, `Narrative:`, `Action item:`. The question was about a
property the bundle removes before anyone reads it, so it was answered from priors, and two
sets of priors gave two answers every time. The second fault: action items are prescriptive
by design, so an assessor counting them as "what should have happened" grades weak and one
excluding them grades adequate. Nothing in the wording said which.

The rewrite names the record to read, gives examples of what to look for, and says
explicitly to ignore the action items because they are graded elsewhere. Measured on four
documents, one run each:

| Document | Narrative | Old wording | New wording |
|---|---|---|---|
| three published status page entries | chronological updates, no hypotheticals | contested on 2 of 3 | **strong**, both raters, all three |
| `fixtures/alternate-reality/rca-hypothetical.json` | "had the lock timeout been set... the team should have caught this" | not run | **weak**, both raters |

Four agreements out of four, and it separates them rather than agreeing on everything. It
also cost $0.079 against the old wording's $0.136 for the same three documents, which is
the cost signal below pointing the same way.

**The negative fixture had to be built.** No document in the shipped corpus has a narrative
that slips into the hypothetical, so a run over the corpus would have graded everything
strong and shown nothing. That absence is worth noticing on its own: the corpus exercised
every structural check and not this dimension.

**One run of four documents is not a golden set.** It is enough to show the old wording was
the problem and not the models. It is not enough to say the new wording is right, and
nothing here measures whether `strong` and `weak` were the correct answers.

## What you can argue with

```bash
cat rca_agent/rubric.toml
```

Required timeline moments, blame phrases, the export window, the minimum number of
contributing factors, and the grade scale. Every setting carries either its source or its
reasoning in a comment beside it, so a disagreement is with a line in a file rather than
with a branch in the code. Organisations name their timeline moments differently, and a
rubric that insists on someone else's vocabulary gets ignored:

```bash
cp rca_agent/rubric.toml /tmp/ours.toml
# edit /tmp/ours.toml, then:
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/corpus \
  --as-of 2026-09-01 --rubric /tmp/ours.toml
```

The rubric is grounded in published practice rather than invented:

| Source | What it contributes |
|---|---|
| PagerDuty, *Effective Postmortems* | Avoid the concept of human error: mistakes result from multiple contributing factors, not one person's actions. Keep the description of the actual problem separate from hypothetical fixes |
| PagerDuty postmortem template | Contributing factors must include actions taken during response that made things worse. Action items fall in four categories: prevent, prepare, process, comms. Each is a ticket |
| incident.io post-incident flow | Follow-ups are first-class objects with owners and due dates, exported to a tracker within a window of closure |

Where this departs from a source, the departure is in the config rather than buried in a
branch.

## The paid path

```bash
uv pip install -e ".[dev,providers]"
cp .env.example .env    # paste ANTHROPIC_API_KEY and GEMINI_API_KEY, or export them;
                        # an export always wins

.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/corpus --check
```

Without those two keys, every paid command stops immediately and says which is missing.
`--check` probes each configured model with one minimal call for about $0.0003 and stops,
which is what a failing run would otherwise have cost you to discover.

**The judged pass assesses every review in the corpus**, so point `--corpus` at a directory
holding one file unless you want to pay for eight:

```bash
mkdir -p /tmp/one && cp rca_agent/fixtures/corpus/rca-hollow.json /tmp/one/
.venv/bin/python -m rca_agent --corpus /tmp/one --as-of 2026-09-01 --judgement
```

Three dimensions, each through two independent assessors and a blind judge, so nine calls
and about 9 cents for one review: $0.0901 on 14 September 2026, of which the contested
dimension was $0.0419. The probe runs first anyway and aborts before the paid pass if a
model is unreachable. Progress goes to stderr with a running cost, and the report
names the assessors and the judge.

Watch `rca-hollow`. It is the case where the structural checks are silent and the judgement
layer is the only thing between a fluent document and a repeat incident.

### It will not pay to grade a document that is not a review

```bash
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/not-a-review \
  --as-of 2026-09-14 --judgement
```

```
  Judgement dimensions

    not judged: this document records no contributing factors and no action
    items. Grading the depth of an analysis that is not there would cost money
    and tell you what the structural pass above already has.
```

Zero judgement calls, and the free structural pass still runs and still reports. The
preflight probe does run first, three calls for about $0.0003, because it checks the models
are reachable before the loop starts and it cannot know in advance that the loop will not
need them. That is the whole spend: $0.0003 against $0.0901 a review. This exists because
it did the opposite: pointed at three published status page entries, it spent
$0.2817 having two vendors and a judge grade the depth of analysis in documents recording
no contributing factor, no action item and no participant. Every dimension came back weak
or contested, which the free pass had established first and for nothing.

The bar is in [`rubric.toml`](rubric.toml) as `judgement_requires_any`, and it is **any one
of them present**, not all. A review with action items has committed to work and the actions
dimension has something to read; one with contributing factors has recorded an analysis and
the cause dimension has something to read. Both absent means the document states neither why
it happened nor what anyone will do.

It is not a structural defect and does not reach `--fail-on-defects`: a defect is a finding
about a review, and this is a statement that the thing is not one. Empty the list to switch
it off, or overrule it per run:

```bash
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/not-a-review \
  --as-of 2026-09-14 --judgement --judge-anyway
```

### Cost may be a leading indicator of an ambiguous rubric

From one live run, output tokens per dimension while input stayed flat at 858-877:

| dimension | opus rater | gemini rater | sonnet judge |
|---|---|---|---|
| cause_not_trigger | 466 | 486 | 257 |
| **no_alternate_reality** (halted, assessors split) | **1017** | **684** | **1490** |
| actions_would_prevent | 443 | 630 | 370 |

The models wrote more when the answer was not clear, and the judge wrote nearly six times
more. Across three runs of the same document, `no_alternate_reality` cost twice the other
two dimensions every time, with input flat to within 2%. If that holds more widely, a
dimension's cost tells you the rubric does not discriminate before anyone reads the output.

It held here. That dimension was the ambiguous one, it was rewritten for the reasons above,
and the rewritten wording cost $0.079 against $0.136 for the same three documents. One
before-and-after is not a law, but the signal pointed at the right dimension.

Three runs of one document is an observation, not a threshold. Recovering even this table
meant inferring the dimension from row order, so ledger rows now record the rubric they
assessed:

```bash
.venv/bin/python -c "import json,collections; c=collections.Counter(); \
[c.update({json.loads(l).get('rubric'): json.loads(l)['cost']}) for l in open('.ledger/calls.jsonl')]; \
print(c)"
```

The file only exists after a paid run, so on a fresh checkout that command raises
`FileNotFoundError`, which is the correct answer to "what have I spent". Rows under `None`
are from runs made before the rubric field existed, and they are why it exists.

The wiring from `argv` into the paid layer is covered by
`tests/integration/test_paid_paths_end_to_end.py`: 9 tests that drive this flag against a fake
provider and a fake probe, with no network and no key. Coverage found that gap. Both CLIs sat
under 56% because every test of the judgement logic called it directly rather than through the
command line, which left the credential check, the preflight and the provider wiring untested.
Those are the lines every failure of the first live run happened in.

## What it does not do

- **It cannot tell a stable disagreement from a coin flip.** A split that reproduces means
  the models read the rubric the same way every time and differently from each other. A
  split that flaps is sampling noise. Every run here is independent and nothing compares
  them, so both are reported identically. On `no_alternate_reality` the split reproduced,
  run after run, and that pattern is what identified the rubric as the problem rather than
  the models. **A person noticed it across runs. Nothing in the tool does**, because
  separating the two means deciding how many repeats are worth paying for, and that is a
  judgement about a corpus this repository does not have.
- **It does not write RCAs.** `python -m rca_agent.draft` has an agent draft one from raw
  incident artifacts and then runs this eval over what it just wrote, but drafting is not a
  feature here: an agent-written RCA is precisely the artifact the eval exists to doubt.
- **The corpus is synthetic.** No real incident data is in this repository. It has been run
  against published incident reports, which is where two of the checks above were found
  misfiring and where the rubric rewrite came from, but none of those documents are here.
- **Not production-tested.** Built in a week, and nobody runs it on a schedule.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_structure.py tests/unit/test_rubric.py \
  tests/unit/test_completion.py tests/unit/test_rca_report.py tests/unit/test_rca_types.py tests/unit/test_blame_needs_a_person.py \
  tests/unit/test_export_breach_needs_followups.py tests/unit/test_worth_judging.py \
  tests/unit/test_judgement_criteria.py \
  tests/integration/test_corpus.py tests/integration/test_judgement.py \
  tests/integration/test_rca_gate.py tests/integration/test_judgement_bar.py
```

111 tests, offline, no credentials. `tests/integration/test_corpus.py` is the one asserting
that each fixture fails only the check it was built to fail.

## Dependencies

Standard library only, plus `ensemble` and `ledger`. Rubric config is TOML via `tomllib`.
The judgement pass needs `litellm`, which arrives with the `providers` extra and not with
the default `dev` install. Check with `uv pip show litellm`.
