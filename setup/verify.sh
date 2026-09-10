#!/usr/bin/env bash
# Runs setup/README.md's own step blocks against an empty Claude Code profile, twice, then
# compares the result with a reference profile. It never prints a key, a header value or
# the contents of a settings file, because a reference profile may hold secrets.
#
#   setup/verify.sh [empty-profile] [reference-profile]
#
#   empty-profile      default: a new temporary directory. It may already hold Claude
#                      Code's own bootstrap files, but not a settings.json.
#   reference-profile  default: the profile this machine uses, ~/.claude plus ~/.claude.json.
#   VERIFY_README      runs a different copy of the document, so a deliberately broken copy
#                      can prove the comparison fails.
#
# Needs claude, jq, curl, and network access to GitHub and Context7. Makes no model call.
# Contract: specs/010-executable-setup/contracts/step-blocks.md
set -euo pipefail

readme=${VERIFY_README:-$(cd "$(dirname "$0")" && pwd)/README.md}
clean=${1:-$(mktemp -d)}
ref=${2:-}

[ -f "$readme" ] || { echo "No document at $readme" >&2; exit 2; }
mkdir -p "$clean"
clean=$(cd "$clean" && pwd)
[ ! -e "$clean/settings.json" ] || { echo "$clean is not empty: it has a settings.json" >&2; exit 2; }
start_state=$(ls -A "$clean" | tr '\n' ' ')

# With CLAUDE_CONFIG_DIR set, Claude Code keeps .claude.json inside that directory. Unset,
# it keeps it at ~/.claude.json. So the default reference is reached by unsetting the
# variable, never by pointing it at ~/.claude.
if [ -n "$ref" ]; then
  ref=$(cd "$ref" && pwd)
  ref_json=$ref/.claude.json
  ref_env=(env CLAUDE_CONFIG_DIR="$ref")
  ref_name=$ref
else
  ref=$HOME/.claude
  ref_json=$HOME/.claude.json
  ref_env=(env -u CLAUDE_CONFIG_DIR)
  ref_name="this machine's profile, ~/.claude and ~/.claude.json"
fi
clean_json=$clean/.claude.json
clean_env=(env CLAUDE_CONFIG_DIR="$clean")

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Extract the executable blocks exactly as the contract defines them.
awk -v dir="$work" '
  /^```bash[ \t]*$/ { inblock = 1; first = 1; out = ""; next }
  inblock && /^```[ \t]*$/ { inblock = 0; if (out != "") close(out); next }
  inblock && first {
    first = 0
    if ($0 ~ /^# step [0-9]+: /) { n++; out = sprintf("%s/step-%02d.sh", dir, n) }
    else if ($0 ~ /^# check/) { out = dir "/check.sh" }
  }
  inblock && out != "" { print > out }
' "$readme"

steps=("$work"/step-*.sh)
[ -e "${steps[0]}" ] || { echo "No step blocks in $readme" >&2; exit 1; }
[ -e "$work/check.sh" ] || { echo "No check block in $readme" >&2; exit 1; }

echo "setup/verify.sh, $(date -u +%Y-%m-%dT%H:%M:%SZ), Claude Code $(claude --version | cut -d' ' -f1)"
echo "document:      $readme"
echo "empty profile: $clean, holding at start: ${start_state:-nothing}"
echo "reference:     $ref_name"
echo

say() { printf '%-8s%s\n' "$1" "$2"; }
fails=0
match() { say MATCH "$1"; }
differ() { say DIFFER "$1"; fails=$((fails + 1)); }

# Each block runs in a fresh shell, as each Bash call in a Claude Code session does. The
# key is a placeholder: the check further down must reject it.
export CONTEXT7_API_KEY=not-a-real-key
for pass in 1 2; do
  for step in "${steps[@]}"; do
    if ! "${clean_env[@]}" bash -euo pipefail "$step" </dev/null >"$work/out" 2>&1; then
      say FAILED "$(head -1 "$step" | cut -c3-), on pass $pass. Its output:"
      sed 's/^/        /' "$work/out"
      exit 1
    fi
  done
done
say RAN "${#steps[@]} steps, twice, against the empty profile. Both passes succeeded."

for f in settings.json rules/context7.md skills/context7-mcp/SKILL.md; do
  if cmp -s "$ref/$f" "$clean/$f"; then
    match "$f, byte for byte"
  else
    differ "$f. Compare locally: diff $ref/$f $clean/$f"
  fi
done

for event in $(jq -r '.hooks // {} | keys[]' "$ref/settings.json"); do
  a=$(jq -cS --arg e "$event" '.hooks[$e]' "$ref/settings.json")
  b=$(jq -cS --arg e "$event" '.hooks[$e] // null' "$clean/settings.json" 2>/dev/null || true)
  if [ "$a" = "$b" ]; then match "hook $event, defined in settings.json"
  else differ "hook $event, defined in settings.json"; fi
done

# Header and environment values are replaced on both sides before comparing, so a key is
# neither compared nor printed.
redact='(.mcpServers // {}) | map_values(
  (if .headers then .headers |= map_values("<redacted>") else . end)
  | (if .env then .env |= map_values("<redacted>") else . end))'
for name in $(jq -r '(.mcpServers // {}) | keys[]' "$ref_json"); do
  a=$(jq -cS --arg n "$name" "$redact | .[\$n]" "$ref_json")
  b=$(jq -cS --arg n "$name" "$redact | .[\$n] // null" "$clean_json" 2>/dev/null || true)
  what=$(jq -r --arg n "$name" '.mcpServers[$n]
    | "\(.type // "stdio") \(.url // .command), header names \((.headers // {}) | keys | join(","))"' \
    "$ref_json")
  if [ "$a" = "$b" ]; then match "mcp server $name: $what. Values not compared"
  else differ "mcp server $name"; fi
done

a=$(jq -cS 'map_values(.source)' "$ref/plugins/known_marketplaces.json")
b=$(jq -cS 'map_values(.source)' "$clean/plugins/known_marketplaces.json" 2>/dev/null || true)
if [ "$a" = "$b" ]; then
  match "plugin marketplaces: $(jq -r 'to_entries | map("\(.key) from \(.value.source.repo // .value.source.url)") | join(", ")' \
    "$ref/plugins/known_marketplaces.json")"
else
  differ "plugin marketplaces"
fi

ref_plugins=$ref/plugins/installed_plugins.json
clean_plugins=$clean/plugins/installed_plugins.json
for p in $(jq -r '.plugins | keys[]' "$ref_plugins"); do
  field() { jq -r --arg p "$p" ".plugins[\$p][0].$2 // \"\"" "$1" 2>/dev/null || true; }
  rv=$(field "$ref_plugins" version); cv=$(field "$clean_plugins" version)
  rp=$(field "$ref_plugins" installPath); cp_=$(field "$clean_plugins" installPath)
  if [ -n "$cp_" ] && [ "$rv" = "$cv" ] && diff -rq -x .in_use -x .git "$rp" "$cp_" >/dev/null 2>&1
  then match "plugin $p $rv, files identical (.git and .in_use aside)"
  else differ "plugin $p: reference ${rv:-absent}, fresh install ${cv:-absent}"; fi
  rs=$(field "$ref_plugins" gitCommitSha | cut -c1-7); cs=$(field "$clean_plugins" gitCommitSha | cut -c1-7)
  [ "$rs" = "$cs" ] || say NOTE "plugin $p recorded commit: reference $rs, fresh install $cs, with the files compared above"
  if [ -f "$rp/hooks/hooks.json" ]; then
    for event in $(jq -r '.hooks | keys[]' "$rp/hooks/hooks.json"); do
      if [ -n "$cp_" ] && cmp -s "$rp/hooks/hooks.json" "$cp_/hooks/hooks.json"
      then match "hook $event, installed by $p"
      else differ "hook $event, installed by $p"; fi
    done
  fi
done

plugin_list() { "$@" claude plugin list </dev/null 2>&1 | grep -E 'Version:|Status:|@' | sed 's/^ *//' || true; }
if [ "$(plugin_list "${ref_env[@]}")" = "$(plugin_list "${clean_env[@]}")" ]; then
  match "claude plugin list: same plugins, versions and enabled state"
else
  differ "claude plugin list"
fi

mcp_list() { "$@" claude mcp list </dev/null 2>/dev/null | grep -E ' - (✔|✗|!) ' || true; }
ref_mcp=$(mcp_list "${ref_env[@]}")
clean_mcp=$(mcp_list "${clean_env[@]}")
while IFS= read -r line; do
  [ -n "$line" ] || continue
  name=${line%%: *}
  state=${line##* - }
  if grep -qF "$name: " <<<"$clean_mcp"; then
    match "claude mcp list shows $name"
  elif [[ $name == claude.ai* ]]; then
    say ACCOUNT "$name, $state in the reference. It lives in the Anthropic account, not in a file"
  else
    differ "claude mcp list: $name is missing"
  fi
done <<<"$ref_mcp"

# The negative control. The same check must accept the reference's key and reject the
# placeholder, or it has not been shown to tell them apart.
verdict() { "$@" bash -euo pipefail "$work/check.sh" </dev/null 2>&1 | grep -E '^context7 key: ' | head -1 || true; }
rk=$(verdict "${ref_env[@]}")
ck=$(verdict "${clean_env[@]}")
if [ "$rk" = "context7 key: accepted" ] && [ "$ck" = "context7 key: REJECTED" ]; then
  match "context7 key check: reference accepted, placeholder rejected"
else
  differ "context7 key check: reference said '${rk:-nothing}', placeholder said '${ck:-nothing}'"
fi

say NOTE "not compared: history, transcripts, memory, caches and the login. They belong to the machine, not the configuration"
echo
if [ "$fails" -eq 0 ]; then echo "0 differences."; else echo "$fails differences."; fi
[ "$fails" -eq 0 ]
