# rca_agent

Catches the incident review that reads well and says nothing.

## The failure it exists for

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

## The rubric is cited, not invented

| Source | What it contributes |
|---|---|
| PagerDuty, *Effective Postmortems* | Avoid the concept of human error: mistakes result from multiple contributing factors, not one person's actions. Keep the description of the actual problem separate from hypothetical fixes |
| PagerDuty postmortem template | Contributing factors must include actions taken during response that made things worse. Action items fall in four categories: prevent, prepare, process, comms. Each is a ticket |
| incident.io post-incident flow | Follow-ups are first-class objects with owners and due dates, exported to a tracker within a window of closure |

Every setting in `rubric.toml` carries its source in a comment. Where this departs from a
source, the departure is in the config rather than buried in a branch.

## Run it

```bash
uv venv && uv pip install -e ".[dev]"

.venv/bin/python -m rca_agent \
  --corpus rca_agent/fixtures/corpus \
  --as-of 2026-09-01 --completion
```

Offline and instant. These are the checks worth running *before* a debrief is scheduled,
so they cost nothing and wait for nothing.

## Two layers, and the split is the design

**Structural, deterministic, free.** Timeline completeness and ordering. Impact
quantified. Blame language. Action items with an owner, a due date, a tracker reference
and a category. At least one item that actually prevents recurrence. An RCA missing a
detection timestamp does not need a second opinion, and paying for one would be the tool
failing to think.

**Judgement, gated, costs money.** Does the cause stop at the trigger. Is what happened
kept separate from what should have happened. Would the preventive items actually prevent
anything. Each dimension is assessed by two independent models plus a judge, through
[`ensemble`](../ensemble/README.md).

## Blame is detected from language, not names

> "Sam restarted the service" is good practice.
> "Sam failed to check the config" is the failure.

So the check reads a configurable phrase list plus the incident's own participant roster,
over `stated_cause` and `contributing_factors` **only, never the narrative.**

Named-entity recognition over the whole document would flag every timeline entry recording
who did what, which is exactly the blameless detail a good RCA should contain. A check
that misfires there trains people to ignore it, and then it catches nothing at all. There
is a test that puts *"Sam Okafor failed to check the config. Human error throughout."* in
the narrative and asserts no defect is raised.

## `rca-hollow` is the fixture that matters

The corpus has eight reviews. Seven each break one check. The eighth breaks none:

```
rca-hollow    0 structural defects
              stated cause: "A bad deploy went out and caused elevated latency."
```

Four ordered timeline moments. Impact quantified to the user and the minute. Blameless
language. A declared preventive action item. Follow-ups exported on time. It passes
everything, and it explains nothing, because the cause it gives is the trigger.

That fixture is the entire justification for the judgement layer. If it also failed a
structural check, the deterministic layer would catch it first and the models would be
proving something already proven.

## Judgement dimensions are gated one at a time

Not one overall grade. A single grade tells a reviewer nothing about *what to look at*,
and one contested judgement would halt the whole review.

```
cause_not_trigger:      CONTESTED, needs human review
no_alternate_reality:   adequate
actions_would_prevent:  weak
```

A contested dimension gets **no grade at all**. "Adequate", sitting between one assessor's
"weak" and another's "strong", is a number nobody argued for.

## Completion is the figure no single review surfaces

```
Items:                    21
Closed:                   13 (62%)
Median age of open items: 163 days
Closed with no evidence:  1

Export policy breaches:   rca-abandoned
Repeated action items:    "Set a default lock timeout of 5s on all migrations"
```

Closed-with-evidence and closed-without are counted separately, because they are different
claims wearing the same word, and collapsing them lets a team close an item by editing a
field.

A repeated action item is the interesting one. The same commitment appearing in two
reviews is evidence the first attempt never landed.

## Change the rubric

```bash
cat rca_agent/rubric.toml
```

Required timeline moments, blame phrases, export window, grade scale. Organisations name
their timeline moments differently, and a rubric that insists on someone else's vocabulary
gets ignored.

## The judgement pass

```bash
cp .env.example .env    # keys go here, or export them; an export always wins
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/corpus --check
.venv/bin/python -m rca_agent --corpus rca_agent/fixtures/corpus --judgement
```

`--check` probes every configured model for a third of a cent and stops. The judgement
pass runs it first anyway, then prints progress to stderr with a running cost, and names
the assessors and the judge in the report.

Watch `rca-hollow`. It is the case where the structural checks are silent and the
judgement layer is the only thing between a fluent document and a repeat incident.

### Cost may be a leading indicator of an ambiguous rubric

From one live run, output tokens per dimension while input stayed flat at 858-877:

| dimension | opus rater | gemini rater | sonnet judge |
|---|---|---|---|
| cause_not_trigger | 466 | 486 | 257 |
| **no_alternate_reality** (halted, assessors split) | **1017** | **684** | **1490** |
| actions_would_prevent | 443 | 630 | 370 |

The models wrote more when the answer was not clear, and the judge wrote nearly six times
more. If that holds, a dimension's cost tells you the rubric does not discriminate before
anyone reads the output.

Three dimensions of one document is an observation, not a threshold. Recovering even this
table meant inferring the dimension from row order, so ledger rows now record the rubric
they assessed and the question is at least answerable across a corpus.

```bash
python -c "import json,collections; c=collections.Counter(); [c.update({json.loads(l).get('rubric'): json.loads(l)['cost']}) for l in open('.ledger/calls.jsonl')]; print(c)"
```

`python -m rca_agent.draft` goes further: it has an agent draft an RCA from raw incident
artifacts, then runs this eval over what it just wrote. Drafting is not a feature here,
because an agent-written RCA is precisely the artifact the eval exists to doubt.

## Dependencies

Standard library only, plus `ensemble` and `ledger`. Rubric config is TOML via `tomllib`.
The judgement pass needs `litellm`, installed with `pip install -e ".[providers]"`.
