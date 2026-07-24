#!/usr/bin/env bash
# Init must be idempotent: running it twice must leave the same bytes as running it once.
# Two defects broke that, both measured on a live consumer:
#   1. the config.yaml migration appended the same 16 commented placeholders every run,
#      because it looked only for ACTIVE keys and never recognised its own output;
#   2. the two deploy engines each carried their own copy of the ledger help text and
#      disagreed on wording and key order, so the file flipped depending on who wrote last.
set -uo pipefail
SCRIPT_DIR_TEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_TEST/../.." && pwd)"
source "$PROJECT_DIR/bin/set-common.sh"
SCRIPT_DIR="$PROJECT_DIR/bin"; SET_TOOLS_ROOT="$PROJECT_DIR"; DRY_RUN=false
source "$PROJECT_DIR/lib/project/deploy_provenance.sh"

TESTS_RUN=0; TESTS_PASSED=0; TESTS_FAILED=0
test_start() { TESTS_RUN=$((TESTS_RUN+1)); echo -n "Test $TESTS_RUN: $1 ... "; }
test_pass()  { TESTS_PASSED=$((TESTS_PASSED+1)); echo -e "${GREEN}PASS${NC}"; }
test_fail()  { TESTS_FAILED=$((TESTS_FAILED+1)); echo -e "${RED}FAIL${NC}: $1"; }

WORK=$(mktemp -d -t set-idem.XXXXXX); trap 'rm -rf "$WORK"' EXIT

# ── 1. config.yaml migration is idempotent ───────────────────────────────────
YAML="$WORK/config.yaml"
printf 'max_parallel: 2\ndefault_model: opus\n' > "$YAML"

run_migration() {
    "$PROJECT_DIR/bin/set-project" --help >/dev/null 2>&1 || true
    bash -c '
        source "'"$PROJECT_DIR"'/bin/set-common.sh"
        DRY_RUN=false
        eval "$(sed -n "/^_KNOWN_DIRECTIVES=/p;/^_migrate_consumer()/,/^}/p" "'"$PROJECT_DIR"'/bin/set-project")"
        mkdir -p "'"$WORK"'/proj/set/orchestration"
        cp "'"$YAML"'" "'"$WORK"'/proj/set/orchestration/config.yaml"
        _migrate_consumer "'"$WORK"'/proj" "$1" "$2" >/dev/null 2>&1
        cp "'"$WORK"'/proj/set/orchestration/config.yaml" "'"$YAML"'"
    ' _ "$1" "$2"
}

run_migration v1 v2
AFTER_ONE=$(wc -l < "$YAML")
run_migration v2 v3
AFTER_TWO=$(wc -l < "$YAML")

test_start "config: a second migration adds nothing"
if [[ "$AFTER_ONE" -eq "$AFTER_TWO" ]]; then test_pass; else
    test_fail "grew from $AFTER_ONE to $AFTER_TWO lines — placeholders re-appended"
fi

test_start "config: no directive appears twice"
DUPES=$(grep -oE '^#[[:space:]]*[a-z_]+:' "$YAML" 2>/dev/null | sort | uniq -d | wc -l)
if [[ "$DUPES" -eq 0 ]]; then test_pass; else
    test_fail "$DUPES directive(s) present more than once"
fi

test_start "config: the first migration did add the missing directives"
if [[ "$AFTER_ONE" -gt 2 ]]; then test_pass; else
    test_fail "nothing was added at all — the fix must not disable the migration"
fi

test_start "config: the project's active keys are untouched"
if grep -q '^max_parallel: 2$' "$YAML" && grep -q '^default_model: opus$' "$YAML"; then
    test_pass; else test_fail "an existing active key was altered"
fi

# ── 2. both engines write the same ledger bytes ──────────────────────────────
PROJ="$WORK/ledger"; mkdir -p "$PROJ/set" "$PROJ/.claude"
echo "content" > "$PROJ/.claude/a.md"

_pv_begin "$PROJ"
_pv_record ".claude/a.md" "$PROJ/.claude/a.md"
_pv_end
BASH_LEDGER=$(cat "$PROJ/set/.deploy-manifest.json")

rm -f "$PROJ/set/.deploy-manifest.json"
PYTHONPATH="$PROJECT_DIR/lib" python3 -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/lib')
from pathlib import Path
from set_orch.deploy_ledger import DeployLedger
l = DeployLedger(Path('$PROJ'))
l.record('.claude/a.md', Path('$PROJ/.claude/a.md'))
l.save()
" 2>/dev/null
PY_LEDGER=$(cat "$PROJ/set/.deploy-manifest.json" 2>/dev/null)

test_start "ledger: both engines agree on the help text"
B_HELP=$(printf '%s' "$BASH_LEDGER" | python3 -c "import json,sys; print(json.load(sys.stdin).get('_help',''))")
P_HELP=$(printf '%s' "$PY_LEDGER"  | python3 -c "import json,sys; print(json.load(sys.stdin).get('_help',''))")
if [[ "$B_HELP" == "$P_HELP" && -n "$B_HELP" ]]; then test_pass; else
    test_fail "two writers, two texts — the file flips on every init"
fi

test_start "ledger: both engines agree on key order"
B_KEYS=$(printf '%s' "$BASH_LEDGER" | python3 -c "import json,sys; print(','.join(json.load(sys.stdin).keys()))")
P_KEYS=$(printf '%s' "$PY_LEDGER"  | python3 -c "import json,sys; print(','.join(json.load(sys.stdin).keys()))")
if [[ "$B_KEYS" == "$P_KEYS" ]]; then test_pass; else
    test_fail "bash=[$B_KEYS] python=[$P_KEYS] — a diff with nothing behind it"
fi

test_start "ledger: the em dash is written as a character, not an escape"
if ! grep -q 'u2014' "$PROJ/set/.deploy-manifest.json"; then test_pass; else
    test_fail "ensure_ascii escaped it — the engines produce different bytes"
fi

echo
echo "─────────────────────────────────────────"
echo "Tests run: $TESTS_RUN, passed: $TESTS_PASSED, failed: $TESTS_FAILED"
[[ $TESTS_FAILED -eq 0 ]]
