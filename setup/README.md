# Toolchain setup

This is the Claude Code setup I used to build this repository, written so you can run it
rather than take my word for it. Give this file to your own Claude Code and it will set up
the same settings, MCP server and plugins as mine, then check the result. Every step writes
to whichever Claude Code profile is active, so you can try it on a scratch profile before it
touches yours.

## What you get

| Piece | Arrives by | Reproduced |
|---|---|---|
| `settings.json`: models, effort, permission mode, one hook, two plugins switched on | Step 4, verbatim | Byte for byte |
| The Context7 rule, `rules/context7.md` | Step 5, verbatim | Byte for byte |
| The Context7 skill, `skills/context7-mcp/SKILL.md` | Step 6, verbatim | Byte for byte |
| The Context7 MCP server | Step 3 | Yes, carrying your key rather than mine |
| superpowers and frontend-design, with the hook superpowers brings | Step 2 | Yes, at whatever version the marketplace serves that day |
| Spec Kit's ten skills | This repository, in `.claude/skills/` | Yes, by cloning it |
| Gmail, Google Calendar and Google Drive connectors | Your own claude.ai account | No. They belong to an account, not a file |
| Custom keybindings | Nothing | There are none |

## Hand this to Claude Code

Export your Context7 key in the shell you start Claude Code from. The session inherits it
and can use it without the key ever appearing in the conversation.

```text
export CONTEXT7_API_KEY=...     # from your Context7 dashboard
claude
```

Then give it this:

> Follow setup/README.md in this repository. Run each step as its own Bash call, in order,
> then the check. Before step 4, tell me which of my files steps 4 to 6 will replace, and
> wait for my yes.

To see the result before touching your own profile, run `setup/verify.sh` first. It runs
the same steps against a scratch profile and compares the result with yours.

### If you are the Claude Code session reading this

- Run only the fenced blocks whose first line starts `# step`, in order, one Bash call each,
  then the block that starts `# check`. Nothing else in this document is meant to be run.
- Each step is safe to run twice. If one fails, fix the cause and start again from step 1.
- Never print, echo or ask for the Context7 key. Step 3 reads it from `CONTEXT7_API_KEY`. If
  that is unset, stop and ask the person to export it and restart you, or to run step 3 in
  their own terminal.
- Never run `claude mcp get context7`. It prints the key in plain text.
- Steps 4 to 6 replace files. Step 1 has already kept the originals, once, under
  `before-agentic-ops/` in the config directory.

## Before you start

- Claude Code. Verified with 2.1.268, native install, on macOS 26.6.
- `jq` and `curl`. macOS ships both.
- Network access to GitHub, for the plugin marketplace, and to Context7.
- A Context7 key. Context7 also answers with no key at all, but a wrong key is worse than
  none: see [Limitations](#limitations).

Every step writes under `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`, and every `claude` command
honours the same variable. That is what lets `setup/verify.sh` run these exact steps
against a scratch profile.

## Steps

### Step 1: keep what is already there

```bash
# step 1: keep the files steps 4 to 6 replace, once, before anything touches them
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_HOME"
for f in settings.json rules/context7.md skills/context7-mcp/SKILL.md; do
  if [ -f "$CLAUDE_HOME/$f" ] && [ ! -e "$CLAUDE_HOME/before-agentic-ops/$f" ]; then
    mkdir -p "$(dirname "$CLAUDE_HOME/before-agentic-ops/$f")"
    cp "$CLAUDE_HOME/$f" "$CLAUDE_HOME/before-agentic-ops/$f"
  fi
done
```

### Step 2: the plugins

The marketplace is added explicitly. On my machine Claude Code added it by itself; in an
empty profile driven from the command line it did not, and the first install failed. This
comes before the settings because adding the marketplace writes a block into
`settings.json` that mine does not contain. Step 4 then overwrites it.

```bash
# step 2: Anthropic's plugin marketplace, then superpowers and frontend-design
claude plugin marketplace add anthropics/claude-plugins-official
claude plugin install superpowers@claude-plugins-official
claude plugin install frontend-design@claude-plugins-official
```

Installs follow the marketplace, and `claude plugin install` has no way to pin a version.
Verified at superpowers 6.3.0 and frontend-design `3b600518a637`. `claude plugin list` shows
what you got.

### Step 3: the Context7 MCP server

A user-scope HTTP server that sends your key as a header. `claude mcp add` refuses a server
that already exists and `claude mcp remove` fails when there is none, so the removal is
allowed to fail. `claude mcp add` redacts the key in its own output.

```bash
# step 3: Context7 at user scope, with the key from your environment
: "${CONTEXT7_API_KEY:?export CONTEXT7_API_KEY, then start Claude Code again}"
claude mcp remove --scope user context7 >/dev/null 2>&1 || true
claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp \
  --header "CONTEXT7_API_KEY: $CONTEXT7_API_KEY"
```

### Step 4: settings.json

The last write to this file, so it matches mine byte for byte. What each key does is in
[Agent surface](#1-agent-surface-and-its-configuration).

```bash
# step 4: settings.json, verbatim
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
cat > "$CLAUDE_HOME/settings.json" <<'EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "cleanupPeriodDays": 14,
  "env": {
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "80",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "32000",
    "DISABLE_TELEMETRY": "1",
    "DISABLE_ERROR_REPORTING": "1",
    "DISABLE_BUG_COMMAND": "1"
  },
  "includeCoAuthoredBy": false,
  "permissions": {
    "defaultMode": "auto"
  },
  "model": "opus[1m]",
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "afplay /System/Library/Sounds/Blow.aiff 2>/dev/null"
          }
        ]
      }
    ]
  },
  "enabledPlugins": {
    "frontend-design@claude-plugins-official": true,
    "superpowers@claude-plugins-official": true
  },
  "skipDangerousModePermissionPrompt": true,
  "skipWorkflowUsageWarning": true,
  "theme": "auto"
}
EOF
```

### Steps 5 and 6: the Context7 rule and skill

Both are Context7's own files, not mine. They are byte-identical to
[upstash/context7](https://github.com/upstash/context7) at commit `17b864f`, were written to
this machine on 4 May, and are reproduced here verbatim under its MIT licence. The rule
makes Context7 the default for every library, framework, SDK, API and CLI question in every
session. The skill carries the same instruction in a form Claude can invoke.

```bash
# step 5: the Context7 rule, verbatim from upstash/context7 at 17b864f
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_HOME/rules"
cat > "$CLAUDE_HOME/rules/context7.md" <<'EOF'
Use Context7 MCP to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service -- even well-known ones like React, Next.js, Prisma, Express, Tailwind, Django, or Spring Boot. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer -- your training data may not reflect recent changes. Prefer this over web search for library docs.

Do not use for: refactoring, writing scripts from scratch, debugging business logic, code review, or general programming concepts.

## Steps

1. Always start with `resolve-library-id` using the library name and the user's question, unless the user provides an exact library ID in `/org/project` format
2. Pick the best match (ID format: `/org/project`) by: exact name match, description relevance, code snippet count, source reputation (High/Medium preferred), and benchmark score (higher is better). If results don't look right, try alternate names or queries (e.g., "next.js" not "nextjs", or rephrase the question). Use version-specific IDs when the user mentions a version
3. `query-docs` with the selected library ID and the user's full question (not single words)
4. If you weren't satisfied with the answer, call `query-docs` again for the same library with `researchMode: true`. This retries with sandboxed agents that git-pull the actual source repos plus a live web search, then synthesizes a fresh answer. More costly than the default
5. Answer using the fetched docs
EOF
```

```bash
# step 6: the Context7 skill, verbatim from upstash/context7 at 17b864f
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_HOME/skills/context7-mcp"
cat > "$CLAUDE_HOME/skills/context7-mcp/SKILL.md" <<'EOF'
---
name: context7-mcp
description: This skill should be used when the user asks about libraries, frameworks, API references, or needs code examples. Activates for setup questions, code generation involving libraries, or mentions of specific frameworks like React, Vue, Next.js, Prisma, Supabase, etc.
---

When the user asks about libraries, frameworks, or needs code examples, use Context7 to fetch current documentation instead of relying on training data.

## When to Use This Skill

Activate this skill when the user:

- Asks setup or configuration questions ("How do I configure Next.js middleware?")
- Requests code involving libraries ("Write a Prisma query for...")
- Needs API references ("What are the Supabase auth methods?")
- Mentions specific frameworks (React, Vue, Svelte, Express, Tailwind, etc.)

## How to Fetch Documentation

### Step 1: Resolve the Library ID

Call `resolve-library-id` with:

- `libraryName`: The library name extracted from the user's question
- `query`: The user's full question (improves relevance ranking)

### Step 2: Select the Best Match

From the resolution results, choose based on:

- Exact or closest name match to what the user asked for
- Higher benchmark scores indicate better documentation quality
- If the user mentioned a version (e.g., "React 19"), prefer version-specific IDs

### Step 3: Fetch the Documentation

Call `query-docs` with:

- `libraryId`: The selected Context7 library ID (e.g., `/vercel/next.js`)
- `query`: The user's specific question

### Step 3.5: Retry with researchMode if you weren't satisfied

If the default `query-docs` answer didn't satisfy, call `query-docs` **again for the same library** with `researchMode: true`. This retries using sandboxed agents that git-pull the actual source repos plus a live web search, then synthesizes a fresh answer. Do this before giving up or answering from training data. More costly than the default — use it as a targeted retry.

### Step 4: Use the Documentation

Incorporate the fetched documentation into your response:

- Answer the user's question using current, accurate information
- Include relevant code examples from the docs
- Cite the library version when relevant

## Guidelines

- **Be specific**: Pass the user's full question as the query for better results
- **Version awareness**: When users mention versions ("Next.js 15", "React 19"), use version-specific library IDs if available from the resolution step
- **Prefer official sources**: When multiple matches exist, prefer official/primary packages over community forks
EOF
```

Running Context7's own setup CLI instead would not give you this machine's setup. It
fetches the rule from upstream's current master, which has changed three times since: on
4 May, 6 July and 25 July. The first of those removed research mode, three hours after
these files were written here. Both files still tell Claude to retry `query-docs` with
`researchMode: true`, and the server no longer takes that parameter: on 10 September its
`query-docs` tool accepted `libraryId` and `query` and nothing else.

### Check

`claude mcp list` reports Context7 as Connected whatever the key is, a placeholder
included. The last line of this check is the one that means something: it asks Context7 a
real question with the key you configured. No model is called.

```bash
# check
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CLAUDE_JSON="${CLAUDE_CONFIG_DIR:+$CLAUDE_CONFIG_DIR/.claude.json}"
CLAUDE_JSON="${CLAUDE_JSON:-$HOME/.claude.json}"
claude plugin list
claude mcp list
jq -r '"model \(.model), subagents \(.env.CLAUDE_CODE_SUBAGENT_MODEL), hooks on \(.hooks | keys | join(" "))"' \
  "$CLAUDE_HOME/settings.json"
key=$(jq -r '.mcpServers.context7.headers.CONTEXT7_API_KEY // ""' "$CLAUDE_JSON")
[ -n "$key" ] || { echo "context7 key: none configured"; exit 1; }
answer=$(curl -sS -m 30 https://mcp.context7.com/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H "CONTEXT7_API_KEY: $key" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"resolve-library-id","arguments":{"libraryName":"litellm","query":"completion"}}}' \
  || true)
case "$answer" in
  *"Available Libraries"*) echo "context7 key: accepted" ;;
  *"Invalid API key"*) echo "context7 key: REJECTED"; exit 1 ;;
  *) echo "context7 key: no answer from Context7"; exit 1 ;;
esac
```

On my machine it prints:

```text
Installed plugins:

  ❯ frontend-design@claude-plugins-official
    Version: 3b600518a637
    Scope: user
    Status: ✔ enabled

  ❯ superpowers@claude-plugins-official
    Version: 6.3.0
    Scope: user
    Status: ✔ enabled

Checking MCP server health…

claude.ai Google Calendar: https://calendarmcp.googleapis.com/mcp/v1 - ! Needs authentication
claude.ai Gmail: https://gmailmcp.googleapis.com/mcp/v1 - ✔ Connected
claude.ai Google Drive: https://drivemcp.googleapis.com/mcp/v1 - ! Needs authentication
context7: https://mcp.context7.com/mcp (HTTP) - ✔ Connected
model opus[1m], subagents sonnet, hooks on Stop
context7 key: accepted
```

## The toolchain, item by item

### 1. Agent surface and its configuration

Claude Code's command-line interface, 2.1.268, native install, run inside GoLand with
Claude Code's IDE integration connected. It is logged in to a Claude Max subscription, so
every model call it makes goes to Anthropic under that plan: no API key, no Bedrock, no
Vertex. Evidence: `claude --version`, `installMethod` and `organizationType: claude_max` in
`~/.claude.json`, and GoLand's lock file in `~/.claude/ide/`.

**settings.json**, reproduced by step 4. What each key does is taken from Claude Code's
documentation at code.claude.com/docs, read through Context7 on 10 September:

| Key | Value | What it does |
|---|---|---|
| `model` | `opus[1m]` | Main loop on the latest Opus, with the 1M-token context window. The docs say Max plans get 1M context on Opus anyway |
| `env.CLAUDE_CODE_SUBAGENT_MODEL` | `sonnet` | Subagents on the latest Sonnet. The docs rank this above every other way a subagent's model is chosen. See [Models](#5-models-and-routing) |
| `env.CLAUDE_CODE_EFFORT_LEVEL` | `max` | Maximum reasoning effort. `max` is the one level that persists across sessions only when set through this variable |
| `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | `80` | Compacts at 80% of the auto-compact window. It can bring compaction earlier, never later |
| `env.CLAUDE_CODE_MAX_OUTPUT_TOKENS` | `32000` | Caps output for most requests at 32,000 tokens |
| `env.DISABLE_TELEMETRY` | `1` | No usage telemetry, which also turns off session quality surveys |
| `env.DISABLE_ERROR_REPORTING` | `1` | No error reports |
| `env.DISABLE_BUG_COMMAND` | `1` | Removes `/feedback`, `/bug` and `/share` |
| `permissions.defaultMode` | `auto` | Auto mode: a separate classifier model approves or blocks each action instead of prompting, still honouring explicit ask rules. Already the default for interactive sessions on Max |
| `skipDangerousModePermissionPrompt` | `true` | No confirmation before entering bypass-permissions mode. Claude Code writes this itself once that confirmation has been accepted |
| `skipWorkflowUsageWarning` | `true` | Not in Claude Code's settings reference when checked. Reproduced as found |
| `includeCoAuthoredBy` | `false` | No Claude attribution on commits or pull requests. Deprecated in favour of `attribution`, and still honoured |
| `cleanupPeriodDays` | `14` | Transcripts and session data older than 14 days are swept at startup. The default is 30 |
| `hooks` | one, on `Stop` | See [Hooks](#4-hooks) |
| `enabledPlugins` | superpowers, frontend-design | Step 2 installs them. This switches them on |
| `theme` | `auto` | Colour theme matching the terminal's background |
| `$schema` | settings schema | Editor validation only |

**Keybindings**: none. There is no `~/.claude/keybindings.json`, so Claude Code's defaults
apply.

**MCP configuration**: one server, Context7, at user scope in `~/.claude.json`. No
project-level servers: this repository has no `.mcp.json`.

### 2. MCP servers

Two kinds, and they are different things.

**Context7**, reproduced by step 3. It puts current library documentation into the
session, retrieved per question from the library's published documentation, so code is
written against the library as it is rather than as a model remembers it. The rule from
step 5 makes it the default for library, framework, SDK, API and CLI questions, which is
why it gets used without being asked for: 138 calls in the transcripts this machine
retains, counted on 10 September.

The example worth giving comes from the session that built this repository. At
06:14:39Z and 06:14:40Z on 10 September, that session asked Context7 two questions about
LiteLLM, whose adapter it had written the night before: how to read a response's cost,
`completion_cost()` against `response._hidden_params["response_cost"]`, and how to get
structured output, `json_object` against `json_schema` with `supports_response_schema`. At
06:19:04Z, commit `ce66912` changed exactly those two things: cost is now read from
`response._hidden_params["response_cost"]` with `completion_cost()` as the fallback, and
structured output uses a JSON schema in strict mode where the model supports one. Its
message says both came "from checking the library docs rather than trusting what I wrote
from memory". `git show ce66912` has the rest.

**claude.ai connectors**: Gmail, Google Calendar and Google Drive. These are not local
configuration. They belong to the Anthropic account Claude Code is logged in to, which is
why `claude mcp list` shows them on this machine and shows nothing in a logged-out profile.
No file in this repository can reproduce them. Connect your own in your claude.ai account.

On this machine, in the recorded run below, Gmail is connected and Calendar and Drive are
listed as needing authentication. None of the three was called in any transcript this
machine retains. They are configured, not used.

### 3. Top five skills

None is authored. All five are installed. They are ranked by Claude Code's own usage
counter, `skillUsage` in `~/.claude.json`, read on 10 September. It is
cumulative, and its oldest recorded use is from 19 March 2026. Spec Kit is counted once,
because its commands are one tool, recorded under two naming schemes across its versions.

| # | Skill | Installed from | Uses | What it does |
|---|---|---|---|---|
| 1 | Spec Kit: `speckit-specify`, `-plan`, `-tasks`, `-implement` and six more | github/spec-kit 0.16.4, into this repository | 624 | Spec-driven development: specification, plan, tasks, implementation, each a file a human reviews |
| 2 | `superpowers:brainstorming` | superpowers 6.3.0 | 156 | Works out intent, requirements and design before any code |
| 3 | `superpowers:systematic-debugging` | superpowers 6.3.0 | 51 | Investigates a bug or failing test before any fix is proposed |
| 4 | `superpowers:writing-plans` | superpowers 6.3.0 | 44 | Turns a spec into an implementation plan before code is touched |
| 5= | `superpowers:test-driven-development`, `subagent-driven-development`, `dispatching-parallel-agents` | superpowers 6.3.0 | 24 each | Tests before implementation; a plan's tasks run through subagents; independent tasks run in parallel |

Fifth place is a three-way tie and is shown as one.

Two more are installed and fall outside the five: frontend-design, 16 uses, and the Context7
skill from step 6, 5 uses. The counter also records Go skills that belong to another
repository's project configuration. Nothing in this document installs them, so they are
left out.

Spec Kit ships with this repository. To add it to another, at the version verified here:

```text
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.16.4
specify init --here --integration claude --script sh --force
```

Run in a repository holding one file, that pair produced all ten skill files byte-identical
to this repository's. `--force` is there because the directory was not empty.

### 4. Hooks

Two. Pre-commit, session, lifecycle and governance hooks are the categories worth
covering, and this is thin against them: nothing runs at pre-commit, and nothing governs.

| Event | Written by | What it does |
|---|---|---|
| `Stop` | me, in `settings.json` | Plays a sound when Claude finishes responding |
| `SessionStart` | the superpowers plugin | Loads superpowers' `using-superpowers` skill into context at startup, after `/clear`, and after compaction |

The `Stop` hook, as it stands in `settings.json`:

```json
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "afplay /System/Library/Sounds/Blow.aiff 2>/dev/null"
          }
        ]
      }
    ]
  },
```

Per the docs, `Stop` fires when the main agent finishes responding, not on an interrupt or
an API error, and it does not support matchers, so the `"*"` does nothing. `afplay` exists
only on macOS.

The `SessionStart` hook, as superpowers 6.3.0 ships it in `hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" session-start",
            "shell": "bash",
            "async": false
          }
        ]
      }
    ]
  }
}
```

Its script reads the plugin's `skills/using-superpowers/SKILL.md` and returns it as
`additionalContext`, which Claude Code adds to the session's context. The matcher leaves out
the two other session sources, `resume` and `fork`.

**Pre-commit**: none. This repository has no git hooks and no pre-commit configuration.
The checks a pre-commit hook would run, lint, the test suite and the import-boundary
contract test, run in CI on every push instead. That is a gate after the push, not before
the commit.

**Governance**: no hook. What decides whether a tool call runs is Claude Code's auto mode,
switched on in settings: a separate classifier model approves or blocks each action. There
are no allow or deny rules and no `PreToolUse` hook, and `skipDangerousModePermissionPrompt`
removes a confirmation rather than adding one.

### 5. Models and routing

One provider, Anthropic, through the Claude Max subscription Claude Code is logged in to.

| Where | Model | Set by |
|---|---|---|
| Main loop | `opus[1m]`: the latest Opus, 1M-token context window | `model` |
| Subagents | `sonnet`: the latest Sonnet | `env.CLAUDE_CODE_SUBAGENT_MODEL` |
| Reasoning effort | `max` | `env.CLAUDE_CODE_EFFORT_LEVEL` |

The reason, in my words:

> Cost efficiency. Sonnet is cheaper.

What actually ran, counted in the transcripts this machine retains on 10 September:

- **Main loop**: 24,046 messages recorded as `claude-opus-5` and 60 as `claude-opus-5[1m]`.
  Another 382, all in one other project, were `claude-fable-5`.
- **Subagents**: 46 of 47 subagent transcripts ran entirely on `claude-sonnet-5`, 2,837
  messages between them. The oldest are from 4 July and belong to a session last written
  on 6 September.
- **One exception**. The 47th transcript is a built-in Explore agent, started in the
  background in another project on 10 September with no model requested. All
  106 of its messages ran on Opus. The docs say `CLAUDE_CODE_SUBAGENT_MODEL` outranks every
  other way a subagent's model is chosen, and no setting in that project overrides it, so
  this run is unexplained. It is recorded here rather than averaged away.
- The transcripts record the model, not reliably the context window. This session,
  configured as `opus[1m]`, carries the `[1m]` marker on some of its messages and not on
  others.

**The agents in this repository route separately.** `cost_agent` and `rca_agent` reach
models through LiteLLM with their own API keys: raters from Anthropic and Google, and a
judge from Anthropic. That routing and the case for two vendors are in
[ensemble/README.md](../ensemble/README.md).

## Limitations

- **The claude.ai connectors cannot be reproduced from any file.** They live in an
  Anthropic account. On this machine two of the three need authentication, and none was
  used.
- **`claude mcp list` cannot tell you whether a Context7 key works.** It reported Connected
  with a placeholder. The check's last line can. A wrong key is worse than none: Context7
  answers a request with no key, and refuses every one made with a wrong key.
- **Plugin versions follow the marketplace.** Verified at superpowers 6.3.0 and
  frontend-design `3b600518a637`. A later install may get something newer, and there is no
  way to pin.
- **The Context7 rule and skill are out of date upstream.** They reproduce this machine,
  not current Context7. Both still tell Claude to retry with `researchMode: true`, which
  upstream removed on 4 May and the server no longer accepts. What a session does with
  that instruction was not tested.
- **Verified on macOS only.** The `Stop` hook needs `afplay`, which only macOS has.
  Elsewhere the command fails and its error output is discarded. The rest should work on
  Linux and has not been run there.
- **The verification checks configuration, not behaviour.** It never starts a session and
  makes no model call. It shows that the files, the MCP entry and the plugins match. It
  does not show the rule steering a session to Context7, a hook firing, auto mode approving
  anything, or a subagent running on Sonnet. The transcript counts above are the evidence
  for the last of those, and they come from this machine's history, not from the
  verification.
- **One subagent run contradicts the routing**, as described under Models, and its cause is
  not known.
- **The key's route into a session is not verified end to end.** The verifier hands
  `CONTEXT7_API_KEY` straight to each step. That a Claude Code session started from a shell
  passes that shell's exported variables on to its own Bash calls was observed with other
  variables, not with the key itself.
- **Step 1 keeps your files; it does not merge them.** Whatever was in your old
  `settings.json` and is not in mine is in `before-agentic-ops/`, not in the live file.
- **This document goes stale without saying so.** CI cannot see this machine. After any
  change to the setup, run `setup/verify.sh` again: drift shows up as a DIFFER line.

## How this was verified

`setup/verify.sh` pulls this document's own `# step` blocks out, runs them twice against an
empty profile, and compares the result with a reference profile, one line per item. It
never prints a key, a header value or the contents of a settings file. What it relies on is shared with
this document and with `tests/unit/test_setup_readme.py`: every executable block is fenced
bash, numbered `# step N:`, and writes only under the active profile.

The recorded run, against the empty profile `/tmp/claude-clean-verify` and compared with
this machine's own profile:

```text
setup/verify.sh, 2026-09-10T22:57:50Z, Claude Code 2.1.268
document:      setup/README.md
empty profile: /tmp/claude-clean-verify, holding at start: .claude.json backups
reference:     this machine's profile, ~/.claude and ~/.claude.json

RAN     6 steps, twice, against the empty profile. Both passes succeeded.
MATCH   settings.json, byte for byte
MATCH   rules/context7.md, byte for byte
MATCH   skills/context7-mcp/SKILL.md, byte for byte
MATCH   hook Stop, defined in settings.json
MATCH   mcp server context7: http https://mcp.context7.com/mcp, header names CONTEXT7_API_KEY. Values not compared
MATCH   plugin marketplaces: claude-plugins-official from anthropics/claude-plugins-official
MATCH   plugin frontend-design@claude-plugins-official 3b600518a637, files identical (.git and .in_use aside)
NOTE    plugin frontend-design@claude-plugins-official recorded commit: reference d53f6ca, fresh install 3b60051, with the files compared above
MATCH   plugin superpowers@claude-plugins-official 6.3.0, files identical (.git and .in_use aside)
NOTE    plugin superpowers@claude-plugins-official recorded commit: reference 7e51643, fresh install b36e082, with the files compared above
MATCH   hook SessionStart, installed by superpowers@claude-plugins-official
MATCH   claude plugin list: same plugins, versions and enabled state
ACCOUNT claude.ai Google Calendar, ! Needs authentication in the reference. It lives in the Anthropic account, not in a file
ACCOUNT claude.ai Gmail, ✔ Connected in the reference. It lives in the Anthropic account, not in a file
ACCOUNT claude.ai Google Drive, ! Needs authentication in the reference. It lives in the Anthropic account, not in a file
MATCH   claude mcp list shows context7
MATCH   context7 key check: reference accepted, placeholder rejected
NOTE    not compared: history, transcripts, memory, caches and the login. They belong to the machine, not the configuration

0 differences.
```

Run it again with:

```text
setup/verify.sh                               # a fresh temporary profile, compared with yours
setup/verify.sh /tmp/claude-clean-verify      # the profile the recorded run used
```

On another machine it compares against that machine's profile, so it answers a different
question: whether your configuration is what this document produces.

It has also been seen to fail. Against a copy of this document with one character changed
inside the settings block, `cleanupPeriodDays` from 14 to 15, it reported
`DIFFER settings.json` and exited 1. With a key-shaped string planted under `setup/`, the
offline secret scan failed and named the file.

## Attribution

The Context7 rule and skill in steps 5 and 6 are Upstash's, from
[upstash/context7](https://github.com/upstash/context7) at commit `17b864f`, copyright 2021
Upstash, Inc., reproduced verbatim under the
[MIT licence](https://github.com/upstash/context7/blob/master/LICENSE).
