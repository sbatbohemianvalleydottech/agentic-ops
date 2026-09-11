<!--
Sync Impact Report
Version change: 1.0.0 → 1.0.1 (PATCH, wording)
Modified principles:
  - IV. One-Way Dependencies: now names the shared primitives that exist. It named
    connectors/, which was planned and never built, and left out ledger/, which the
    contract test already protects. What the principle requires is unchanged.
Added sections: none
Removed sections: none
Templates requiring review: none. plan-template, spec-template and tasks-template read
  this file at runtime; no changes made to them here.
Deferred TODOs: none
-->

# agentic-ops Constitution

## Core Principles

### I. No Single Model Decides (NON-NEGOTIABLE)

Every consequential judgement MUST be produced by at least two independent raters and
assessed by an independent judge. The judge MUST NOT be told whether the raters agreed;
it answers a different question, namely whether the evidence supports the grade under the
stated rubric. Rater disagreement MUST halt the workflow. Unanimous raters overruled by
the judge MUST also halt. Grades MUST NEVER be averaged, rounded, or otherwise resolved
automatically.

Rationale: an agent's most dangerous failure is a confident wrong answer returned
successfully. Comparison alone cannot catch two models being wrong in the same direction,
which is exactly the failure that correlated training lineage makes likely. Averaging
destroys the only signal that something needs a human.

### II. Evidence or Silence

Every claim in any generated output MUST cite the evidence record that supports it. A
claim that cannot cite MUST be dropped, not softened, hedged, or rephrased. Evidence
records MUST carry their source, timestamp and a resolvable reference.

Rationale: a performance grade or a savings figure has to survive being disputed by the
person it describes or the engineer who owns the resource. An uncitable claim is a
liability, not a finding.

### III. Test-First (NON-NEGOTIABLE)

No production code without a failing test first. The cycle is: write one minimal test,
run it, watch it fail for the right reason, write the least code that passes, confirm
green. Code written before its test MUST be deleted and rewritten from the test.

Rationale: a test written after the code passes immediately, which proves nothing about
whether it can catch the bug it claims to cover.

### IV. One-Way Dependencies

`ensemble/` and `ledger/`, the shared primitives, MUST NOT import from any agent package.
Dependencies point one way only, from agents to shared primitives. This MUST be enforced
by an automated check in CI, not by review.

Rationale: this is the whole difference between reusable artifacts and one application
split across three folders. It is a checkable property, so it MUST be checked rather
than asserted.

### V. Humans Decide, Agents Propose

No artifact in this repository MAY write a final judgement about a person, close an
action item, or apply a spend change. Agents produce a proposal, the evidence behind it,
and a gate decision. A human makes the call.

Rationale: the human gate is the design, not a limitation of the current implementation.
Removing it would not be an improvement, it would be a different and worse system.

## Evidence and Data Constraints

All data in this repository MUST be synthetic. No employer data, configuration, source
code or customer information may be committed, including in fixtures, test data or
documentation.

Connectors MUST match the tool surface of the real systems they stand in for, but MUST
be clearly labelled as fixture-backed. No README, docstring or output may imply a live
enterprise connection.

Classification and grading logic MUST operate on thresholds and observable properties,
never on hardcoded identities. Pointing an agent at a different estate MUST produce
different findings. Every rule MUST be exercised by a second, unrelated fixture that
proves it generalises.

Every model call MUST be metered to the cost ledger. Secrets MUST be read from the
environment and MUST NEVER be committed.

## Development Workflow

Work proceeds through Spec Kit: constitution, then `/speckit-specify`, `/speckit-plan`,
`/speckit-tasks`, `/speckit-implement`, in that order. Implementation follows Principle
III within each task.

CI MUST enforce, as blocking checks: the full test suite, and the one-way import rule
from Principle IV.

Each artifact directory MUST carry its own README stating what it does, how to run it
alone, and what it depends on. An artifact that cannot be run without the others has
violated Principle IV.

## Governance

This constitution supersedes other practices in this repository. Where a Spec Kit
template, a generated plan or a task conflicts with a principle here, this document wins
and the conflict MUST be raised rather than silently resolved.

Amendments require an explicit version bump and an entry in the Sync Impact Report at
the top of this file. Versioning is semantic: MAJOR for removing or redefining a
principle, MINOR for adding one or materially expanding guidance, PATCH for
clarifications and wording.

Compliance is verified at review time. Any complexity that appears to violate a
principle MUST be justified in the plan's Complexity Tracking section or removed.

**Version**: 1.0.1 | **Ratified**: 2026-09-09 | **Last Amended**: 2026-09-11
