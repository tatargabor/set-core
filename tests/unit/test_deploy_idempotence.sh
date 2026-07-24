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

# ── 3. an init that changes nothing rewrites nothing ─────────────────────────
#
# `updated` records when the content last changed, so it must not be the thing that
# makes it change. While it was stamped unconditionally, an empty `git status` could
# never be the proof that a deploy was a no-op — a consumer had to filter one line by
# hand to see it.

PROJ2="$WORK/quiet"; mkdir -p "$PROJ2/set" "$PROJ2/.claude"
echo "content" > "$PROJ2/.claude/a.md"

_pv_begin "$PROJ2"; _pv_record ".claude/a.md" "$PROJ2/.claude/a.md"; _pv_end
FIRST=$(sha256sum "$PROJ2/set/.deploy-manifest.json" | cut -d' ' -f1)
sleep 1
_pv_begin "$PROJ2"; _pv_record ".claude/a.md" "$PROJ2/.claude/a.md"; _pv_end
SECOND=$(sha256sum "$PROJ2/set/.deploy-manifest.json" | cut -d' ' -f1)

test_start "ledger: re-recording identical content leaves the file byte-identical"
if [[ "$FIRST" == "$SECOND" ]]; then test_pass; else
    test_fail "the timestamp alone rewrote it — git status can never prove a no-op"
fi

echo "changed" > "$PROJ2/.claude/a.md"
_pv_begin "$PROJ2"; _pv_record ".claude/a.md" "$PROJ2/.claude/a.md"; _pv_end
THIRD=$(sha256sum "$PROJ2/set/.deploy-manifest.json" | cut -d' ' -f1)

test_start "ledger: a real content change DOES rewrite it"
if [[ "$SECOND" != "$THIRD" ]]; then test_pass; else
    test_fail "suppressing the no-op write must not suppress a real one"
fi

test_start "ledger: and the new hash is actually recorded"
if grep -q "$(sha256sum "$PROJ2/.claude/a.md" | cut -d' ' -f1)" "$PROJ2/set/.deploy-manifest.json"; then
    test_pass; else test_fail "the ledger no longer matches what is on disk"
fi

test_start "ledger: the python engine agrees — identical content, no rewrite"
PY_OUT=$(python3 -c "
import sys, time; sys.path.insert(0, '$PROJECT_DIR/lib')
from pathlib import Path
from set_orch.deploy_ledger import DeployLedger
p = Path('$WORK/pyquiet'); (p / '.claude').mkdir(parents=True, exist_ok=True)
(p / '.claude/a.md').write_text('x')
for _ in range(2):
    l = DeployLedger(p); l.record('.claude/a.md', p / '.claude/a.md'); wrote = l.save()
print('second_write' if wrote else 'quiet')
" 2>&1 | tail -1)
if [[ "$PY_OUT" == "quiet" ]]; then test_pass; else
    test_fail "python engine still rewrites an unchanged ledger ($PY_OUT)"
fi

# ── 4. absence of a git-ignored path is not a decision ───────────────────────
#
# Found by running init on a throwaway clone after `git clean -fd`: `.set/reflection.md`
# is gitignored, so the clean removed it, and the deploy read that as "the project
# deleted this" and tombstoned it. A routine housekeeping command would have retired
# the file permanently — and the git-history rule cannot rescue it, because an ignored
# path never appears in history at all.

GPROJ="$WORK/ignored"; mkdir -p "$GPROJ/.set" "$GPROJ/set"
git -C "$GPROJ" init -q 2>/dev/null
printf '/.set/\n' > "$GPROJ/.gitignore"
printf 'tracked\n' > "$GPROJ/kept.md"
echo "reflection" > "$GPROJ/.set/reflection.md"

_pv_begin "$GPROJ"
_pv_record ".set/reflection.md" "$GPROJ/.set/reflection.md"
_pv_record "kept.md" "$GPROJ/kept.md"
_pv_end

rm -f "$GPROJ/.set/reflection.md" "$GPROJ/kept.md"   # what `git clean -fd` + a delete do

_pv_begin "$GPROJ"
IGN_REASON=$(_pv_should_deploy ".set/reflection.md" "$GPROJ/.set/reflection.md"; echo "rc=$?")
TRK_REASON=$(_pv_should_deploy "kept.md" "$GPROJ/kept.md"; echo "rc=$?")
_pv_end

test_start "ignored: an absent git-ignored path is redeployed, not tombstoned"
if [[ "$IGN_REASON" == "rc=0" ]]; then test_pass; else
    test_fail "got [$IGN_REASON] — a git clean would retire the file forever"
fi

test_start "ignored: an absent TRACKED path is still tombstoned"
if [[ "$TRK_REASON" == *"rc=1"* && "$TRK_REASON" == *tombstone* ]]; then test_pass; else
    test_fail "got [$TRK_REASON] — the deletion signal must keep working"
fi

test_start "ignored: the tombstone list did not gain the ignored path"
TOMBS=$(python3 -c "
import json,sys
print(','.join(json.load(open(sys.argv[1])).get('tombstones', [])))
" "$GPROJ/set/.deploy-manifest.json" 2>/dev/null)
if [[ "$TOMBS" != *reflection* ]]; then test_pass; else
    test_fail "the ignored path was tombstoned anyway (tombstones=[$TOMBS])"
fi

test_start "ignored: the tracked deletion IS in the tombstone list"
if [[ "$TOMBS" == *kept.md* ]]; then test_pass; else
    test_fail "the real deletion was not recorded (tombstones=[$TOMBS])"
fi

# The same path may ALSO appear in git history as deleted — that history is about the
# era when it was tracked, before the ignore rule existed. Measured on a real consumer:
# the agent learning file had to move out of `.claude/` (Claude Code blocks writes
# there), so its move reads as a deletion, and the git-history rule retired it for good.
HPROJ="$WORK/ignored-history"; mkdir -p "$HPROJ/set"
git -C "$HPROJ" init -q 2>/dev/null
git -C "$HPROJ" config user.email t@e; git -C "$HPROJ" config user.name t
mkdir -p "$HPROJ/.set"; echo "old home" > "$HPROJ/.set/reflection.md"
git -C "$HPROJ" add -A -f >/dev/null 2>&1; git -C "$HPROJ" commit -qm "tracked once" >/dev/null 2>&1
git -C "$HPROJ" rm -q "$HPROJ/.set/reflection.md" >/dev/null 2>&1
printf '/.set/\n' > "$HPROJ/.gitignore"
git -C "$HPROJ" add -A >/dev/null 2>&1
git -C "$HPROJ" commit -qm "move out of tracking, ignore it" >/dev/null 2>&1

_pv_begin "$HPROJ"
HIST_RC=$(_pv_should_deploy ".set/reflection.md" "$HPROJ/.set/reflection.md" >/dev/null; echo "rc=$?")
_pv_end

test_start "ignored: a git-history deletion does not tombstone a now-ignored path"
if [[ "$HIST_RC" == "rc=0" ]]; then test_pass; else
    test_fail "got [$HIST_RC] — the history rule read a move as a rejection"
fi

echo
echo "─────────────────────────────────────────"
echo "Tests run: $TESTS_RUN, passed: $TESTS_PASSED, failed: $TESTS_FAILED"
[[ $TESTS_FAILED -eq 0 ]]
