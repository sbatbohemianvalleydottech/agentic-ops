# The cold-read prompt

Paste this at a capable agent, or hand it to a colleague who has not seen this repository.
Replace the three values in `<angle brackets>`. One reader per document.

The protocol and what it has found are in [`COLD-READ.md`](../COLD-READ.md).

---

You are auditing documentation quality by trying to use it. You have NO prior context about
this project and must not acquire any except through the one document named below.

**Setup**

1. Make a fresh clone, so you get the experience of a new reader rather than the author's
   working tree:

   `git clone <REPOSITORY> <SOMEWHERE EMPTY>`

2. If the document has a paid path, copy the credentials in WITHOUT reading or printing them:

   `cp <PATH TO .env> <YOUR CLONE>/.env`

   Never `cat`, `grep`, `echo` or otherwise display that file. It holds live API keys. If any
   key value would appear in your output, stop and redact it.

3. Work only inside your clone.

**Your only document:** `<THE DOCUMENT>` in your clone.

You may follow links that document gives you, and read files it explicitly tells you to open.
You must NOT read any source file, any other package README, the git history, or any test
file unless the document directs you there. If you find yourself guessing, that is a
documentation defect: record it rather than working around it silently.

**Your task**

Get the thing running end to end, including any paid path. Follow the document literally.
When a command fails, or does something other than what the document says, that is the
finding.

**Hard rules**

- Do not modify, create, or delete any file outside your clone. The original repository is
  off limits.
- Never edit source code or tests anywhere, even in your clone. You are testing the document,
  not fixing the project.
- SPEND CAP: `<AMOUNT>`. Paid runs print a running cost to stderr. If it passes the cap, stop
  immediately and report.
- Run each paid path exactly once.

**Report back, precisely**

1. **Command log.** Every command you ran, in order, each marked WORKED or FAILED. Mark the
   command number at which you first got a successful run, and the number at which you first
   got a successful paid run.
2. **Defects.** A numbered list. For each: file and line number where possible, the text that
   is wrong or missing quoted verbatim, what actually happened, and what the document should
   say instead. Include anything you had to guess, anything you backtracked from, and every
   number the document claims that did not match what you observed.
3. **Numbers.** The actual figures the tool printed, and the cost and wall clock of any paid
   run.
4. **Verdict.** Could a competent engineer who has never seen this repository get to a working
   run using this document alone? Yes or no, and the single biggest obstacle.

Be blunt. A defect you soften is a defect that ships.
