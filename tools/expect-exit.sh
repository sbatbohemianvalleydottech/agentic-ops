#!/usr/bin/env bash
# Assert that a command exits with the code the contract says it should.
#
#   tools/expect-exit.sh 1 python -m plan_cost --plan over-budget.json --env staging
#
# Exists because "it ran" and "it ran and said what it should have said" are
# different claims, and a pipeline step that only checks the first will pass a
# gate that has quietly stopped gating. The exit contract is in ci/__init__.py.
set -uo pipefail

expected="$1"; shift
"$@"
actual=$?

meaning=$(python -c "from ci import describe; print(describe($actual))" 2>/dev/null \
          || echo "exit $actual")

if [ "$actual" -eq "$expected" ]; then
  printf '  ok    %s\n        %s\n' "$*" "$meaning"
  exit 0
fi

printf '  FAIL  %s\n        expected exit %s, got %s\n        %s\n' \
  "$*" "$expected" "$actual" "$meaning" >&2
exit 1
