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

That one command prints about 65 lines: a block per review for all eight fixtures, each
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
and a few cents for one review. The probe runs first anyway and aborts before the paid pass
if a model is unreachable. Progress goes to stderr with a running cost, and the report
names the assessors and the judge.

Watch `rca-hollow`. It is the case where the structural checks are silent and the judgement
layer is the only thing between a fluent document and a repeat incident.

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

## What it does not do

- **It cannot tell a stable disagreement from a coin flip.** The same two models reached
  the same two grades in every run: Opus `adequate`, Gemini `strong`. A split that
  reproduces means the models read the rubric differently and consistently, so re-running
  is spend with no information in it. A split that flaps is sampling noise. Every run here
  is independent and nothing compares them, so both are reported identically. Recorded as
  a limitation rather than fixed, because separating them means deciding how many repeats
  are worth paying for, and that is a judgement about a corpus this repository does not
  have.
- **It does not write RCAs.** `python -m rca_agent.draft` has an agent draft one from raw
  incident artifacts and then runs this eval over what it just wrote, but drafting is not a
  feature here: an agent-written RCA is precisely the artifact the eval exists to doubt.
- **The corpus is synthetic.** No real incident data is in this repository.
- **Built in a week for a project.** Not production-tested.

## Run its tests

```bash
.venv/bin/python -m pytest tests/unit/test_structure.py tests/unit/test_rubric.py \
  tests/unit/test_completion.py tests/unit/test_rca_report.py tests/unit/test_rca_types.py \
  tests/integration/test_corpus.py tests/integration/test_judgement.py
```

55 tests, offline, no credentials. `tests/integration/test_corpus.py` is the one asserting
that each fixture fails only the check it was built to fail.

## Dependencies

Standard library only, plus `ensemble` and `ledger`. Rubric config is TOML via `tomllib`.
The judgement pass needs `litellm`, which arrives with the `providers` extra and not with
the default `dev` install. Check with `uv pip show litellm`.
