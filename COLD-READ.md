# Cold reading

**A document is a claim, and its author is the worst person to test it.** You cannot
un-know what you meant. Every gap in a README is invisible to the person who wrote it,
because their head fills it in.

So the documents here are tested the same way the code is: by running them, against
somebody who cannot ask what you meant.

## The protocol

One reader per document. For each:

1. **Fresh clone.** Not the author's working tree. No `.venv`, no `.env`, no `.ledger`, no
   local state that hides a setup step.
2. **One document, and only what it links to.** No source files, no other package README, no
   tests, no commit history. If the reader has to look outside the document, that is the
   finding.
3. **Run it literally.** Follow the commands in the order given. When one fails, or does
   something other than what the document says, record it and carry on.
4. **Record everything.** Every command, marked worked or failed. The command number at
   which the first successful run happened. Every point where the reader guessed or
   backtracked. Every number the document claims that could be checked, and whether it
   matched.
5. **Change nothing.** The reader is testing the document, not fixing the project. A reader
   who silently works around a gap has destroyed the evidence.

A spend cap is set per reader, and paid paths are run exactly once.

The prompt handed to each reader is in [`tools/cold-read-prompt.md`](tools/cold-read-prompt.md).
It is written to be pasted at any capable agent, or given to a colleague who has not seen
the repository.

## What it found on 14 September 2026

Four readers, four documents, about 13 minutes each. Zero commands failed unexpectedly, and
all four reached a working paid run. They still disproved five claims.

| Claim | What actually happened |
|---|---|
| The root README's credentials section was runnable | It sent a reader from the default install straight to a paid command. The provider library is an optional extra, so it stops with `litellm is not installed` |
| `cost_agent` opened with two figures "a reader can reproduce" | No command in the repository printed either. The report aggregates by driver and never shows a per-resource total |
| "Categories with nothing in them are not printed" | Three of the four printed `none`, and the fourth vanished |
| "Two budgets and no name is an error rather than a pick" | It warned on stderr and judged the plan against a **looser** threshold, which is the failure that same document calls impossible |
| `rca_agent` "prints about 65 lines" | It prints 77, and the correct number was already written down one file away |

**Two of those five were defects in the code, not in the prose**: the gate that quietly
relaxed now exits 2, and every category renders. The other three were fixed in the documents,
including the unreproducible headline figures, which are now derivable from two commands the
document hands you rather than from a report that never printed them.

That count was wrong here until an outside reviewer checked it against the commits. It said
three. `git show 54c71fb --stat` is eight markdown files and no source, so it was two. A
document about catching drift, drifting, is the joke it deserves to be, and it is recorded
rather than quietly corrected.

A sixth finding came from the same run: the `ensemble` demo printed nothing to stderr and ran
no preflight, while the root README claimed every paid pass does both. The demo was changed
to match its own documentation rather than the documentation softened to match the demo.

## Why this is not a review

Review catches what a reader thinks is wrong. Cold reading catches what a document does not
say. The corpus miscount in `rca_agent` had already survived one careful correction by the
author and was still wrong; a reader who could not ask a question found it by counting.

The cost is low and the yield is high, so it is worth repeating **after any rewrite**, not
once at the end. The failure mode to avoid is a reader who is too helpful. Instructions say
be blunt, and say that a defect softened is a defect shipped, for that reason.

## What it does not do

- **It does not test the code.** The test suite does that, offline, 460 times.
- **It does not prove a document is good**, only that its instructions execute and its
  checkable numbers hold. Whether the argument is any good is a human's call.
- **Four readers is not a sample.** Two of these five findings would probably have been
  caught by a fifth reader on a document nobody audited. `ledger/README.md` and
  `setup/README.md` have not been through this.
