#!/usr/bin/env bash
# Tests for the deploy provenance ledger (lib/project/deploy_provenance.sh).
#
# The behaviour under test is the one that decides whether `set-project init --force`
# preserves or destroys a consumer's hand-edited .claude/ files. Each case builds a
# throwaway "consumer" tree, runs the guarded deploy, and asserts on file content —
# not on log text, which is why a regression here cannot pass by printing the right words.
#
# Run with: ./tests/unit/test_deploy_provenance.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_DIR/bin/set-common.sh"

SCRIPT_DIR="$PROJECT_DIR/bin"
SET_TOOLS_ROOT="$PROJECT_DIR"
DRY_RUN=false
source "$PROJECT_DIR/lib/project/deploy_provenance.sh"

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

test_start() { TESTS_RUN=$((TESTS_RUN + 1)); echo -n "Test $TESTS_RUN: $1 ... "; }
test_pass()  { TESTS_PASSED=$((TESTS_PASSED + 1)); echo -e "${GREEN}PASS${NC}"; }
test_fail()  { TESTS_FAILED=$((TESTS_FAILED + 1)); echo -e "${RED}FAIL${NC}: $1"; }

assert_content() {
    local file="$1" expected="$2" msg="$3"
    local actual
    actual=$(cat "$file" 2>/dev/null || echo "<missing>")
    if [[ "$actual" == "$expected" ]]; then
        test_pass
    else
        test_fail "$msg (expected '$expected', got '$actual')"
    fi
}

WORK=$(mktemp -d -t set-pv-test.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

# Build a source dir and a consumer project dir for one scenario.
# Echoes "<src> <project>".
new_scenario() {
    local name="$1"
    local src="$WORK/$name/src"
    local proj="$WORK/$name/proj"
    mkdir -p "$src" "$proj"
    echo "$src $proj"
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. First deploy of a file that does not exist yet → written, hash recorded.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario fresh)"
echo "v1" > "$SRC/rule.md"

test_start "fresh file is deployed"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/rules/rule.md" "$SRC/rule.md" "$PROJ/.claude/rules/rule.md"
_pv_end
assert_content "$PROJ/.claude/rules/rule.md" "v1" "fresh file not deployed"

test_start "ledger records the deployed hash"
if [[ -f "$PROJ/set/.deploy-manifest.json" ]] \
    && grep -q '".claude/rules/rule.md"' "$PROJ/set/.deploy-manifest.json"; then
    test_pass
else
    test_fail "ledger missing or has no entry"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. Untouched file + template moved on → UPDATE lands (the anti-freeze case).
#    This is what "skip if exists" would get wrong: the consumer never edited it,
#    so withholding the framework fix would be a bug, not safety.
# ─────────────────────────────────────────────────────────────────────────────
test_start "untouched file receives the framework update"
echo "v2" > "$SRC/rule.md"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/rules/rule.md" "$SRC/rule.md" "$PROJ/.claude/rules/rule.md"
_pv_end
assert_content "$PROJ/.claude/rules/rule.md" "v2" "update did not land on an untouched file"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Consumer edited the file → SKIPPED, edit survives (the core protection).
# ─────────────────────────────────────────────────────────────────────────────
test_start "consumer-edited file is preserved"
echo "MINE — hand edited" > "$PROJ/.claude/rules/rule.md"
echo "v3" > "$SRC/rule.md"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/rules/rule.md" "$SRC/rule.md" "$PROJ/.claude/rules/rule.md"
_pv_end
assert_content "$PROJ/.claude/rules/rule.md" "MINE — hand edited" "consumer edit was clobbered"

test_start "skip is counted"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/rules/rule.md" "$SRC/rule.md" "$PROJ/.claude/rules/rule.md"
if [[ "${_PV_SKIPPED:-0}" -eq 1 ]]; then test_pass; else test_fail "_PV_SKIPPED=${_PV_SKIPPED:-0}, want 1"; fi
_pv_end

# ─────────────────────────────────────────────────────────────────────────────
# 4. Pre-existing file with NO ledger entry → skipped (adoption safety).
#    Every project that predates the ledger looks like this on its first run.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario legacy)"
echo "template" > "$SRC/agent.md"
mkdir -p "$PROJ/.claude/agents"
echo "PROJECT VERSION" > "$PROJ/.claude/agents/agent.md"

test_start "unknown-provenance file is not overwritten"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/agents/agent.md" "$SRC/agent.md" "$PROJ/.claude/agents/agent.md"
_pv_end
assert_content "$PROJ/.claude/agents/agent.md" "PROJECT VERSION" "pre-ledger file was clobbered"

test_start "a skipped file gets no ledger entry"
if [[ ! -f "$PROJ/set/.deploy-manifest.json" ]] \
    || ! grep -q '".claude/agents/agent.md"' "$PROJ/set/.deploy-manifest.json" 2>/dev/null; then
    test_pass
else
    test_fail "skipped file was recorded — next run would overwrite it"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Whole-tree deploy: mixed edited / untouched / new.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario tree)"
mkdir -p "$SRC/sub"
echo "a1" > "$SRC/a.md"
echo "b1" > "$SRC/sub/b.md"

test_start "tree deploy writes all files on first run"
_pv_begin "$PROJ"; _pv_deploy_tree "$SRC" "$PROJ/.claude/skills/set" "$PROJ"; _pv_end
if [[ -f "$PROJ/.claude/skills/set/a.md" ]] && [[ -f "$PROJ/.claude/skills/set/sub/b.md" ]]; then
    test_pass
else
    test_fail "nested tree not fully deployed"
fi

test_start "tree deploy: edited file kept, untouched file updated"
echo "EDITED" > "$PROJ/.claude/skills/set/a.md"
echo "a2" > "$SRC/a.md"
echo "b2" > "$SRC/sub/b.md"
_pv_begin "$PROJ"; _pv_deploy_tree "$SRC" "$PROJ/.claude/skills/set" "$PROJ"; _pv_end
kept=$(cat "$PROJ/.claude/skills/set/a.md")
updated=$(cat "$PROJ/.claude/skills/set/sub/b.md")
if [[ "$kept" == "EDITED" ]] && [[ "$updated" == "b2" ]]; then
    test_pass
else
    test_fail "kept='$kept' (want EDITED), updated='$updated' (want b2)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. DRY_RUN writes nothing at all.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario dryrun)"
echo "new" > "$SRC/x.md"

test_start "dry run creates no files"
DRY_RUN=true
_pv_begin "$PROJ"; _pv_deploy_file ".claude/x.md" "$SRC/x.md" "$PROJ/.claude/x.md"; _pv_end
DRY_RUN=false
if [[ ! -e "$PROJ/.claude/x.md" ]] && [[ ! -e "$PROJ/set/.deploy-manifest.json" ]]; then
    test_pass
else
    test_fail "dry run wrote to disk"
fi

test_start "dry run reports the skip reason"
mkdir -p "$PROJ/.claude"
echo "PROJECT" > "$PROJ/.claude/x.md"
DRY_RUN=true
out=$(_pv_begin "$PROJ"; _pv_deploy_file ".claude/x.md" "$SRC/x.md" "$PROJ/.claude/x.md" 2>&1; _pv_end)
DRY_RUN=false
if [[ "$out" == *"Would skip"* ]] && [[ "$out" == *"unknown provenance"* ]]; then
    test_pass
else
    test_fail "dry-run output lacked the reason: $out"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 7. Self-deploy (source == destination) is a no-op, never a truncation.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario selfdeploy)"
echo "content" > "$SRC/s.md"

test_start "self-deploy leaves the source intact"
_pv_begin "$PROJ"; _pv_deploy_tree "$SRC" "$SRC" "$PROJ"; _pv_end
assert_content "$SRC/s.md" "content" "self-deploy damaged the source"

# ─────────────────────────────────────────────────────────────────────────────
# 8. A symlinked destination directory is replaced, not written through.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario symlink)"
echo "upstream" > "$SRC/l.md"
mkdir -p "$PROJ/.claude"
ln -s "$SRC" "$PROJ/.claude/skills"

test_start "symlinked destination is replaced by a real directory"
_pv_begin "$PROJ"; _pv_deploy_tree "$SRC" "$PROJ/.claude/skills" "$PROJ"; _pv_end
if [[ ! -L "$PROJ/.claude/skills" ]] && [[ -d "$PROJ/.claude/skills" ]]; then
    test_pass
else
    test_fail "destination is still a symlink — writes would leak into set-core"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 9. Ledger merge: entries from an earlier phase survive a later one.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario merge)"
echo "one" > "$SRC/one.md"
echo "two" > "$SRC/two.md"

test_start "ledger keeps entries across deploy phases"
_pv_begin "$PROJ"; _pv_deploy_file "a/one.md" "$SRC/one.md" "$PROJ/a/one.md"; _pv_end
_pv_begin "$PROJ"; _pv_deploy_file "b/two.md" "$SRC/two.md" "$PROJ/b/two.md"; _pv_end
if grep -q '"a/one.md"' "$PROJ/set/.deploy-manifest.json" \
    && grep -q '"b/two.md"' "$PROJ/set/.deploy-manifest.json"; then
    test_pass
else
    test_fail "second phase dropped the first phase's entries"
fi

test_start "ledger is valid JSON with a version"
if python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
assert d['version'] == 2, d.get('version')
assert isinstance(d['files'], dict) and d['files']
assert isinstance(d['tombstones'], list)
assert 'updated' in d and '_help' in d
" "$PROJ/set/.deploy-manifest.json" 2>/dev/null; then
    test_pass
else
    test_fail "ledger is not the expected JSON shape"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 10. A corrupt ledger must not take the deploy down — and must stay conservative.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario corrupt)"
echo "fresh" > "$SRC/c.md"
mkdir -p "$PROJ/set" "$PROJ/.claude"
echo "{ this is not json" > "$PROJ/set/.deploy-manifest.json"
echo "PROJECT" > "$PROJ/.claude/c.md"

test_start "corrupt ledger degrades to skip, not to crash"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/c.md" "$SRC/c.md" "$PROJ/.claude/c.md"
_pv_end
assert_content "$PROJ/.claude/c.md" "PROJECT" "corrupt ledger led to a clobber"

# ─────────────────────────────────────────────────────────────────────────────
# 11. TOMBSTONES — deploy, project deletes, redeploy must NOT resurrect.
#     Measured case: a consumer deleted three set-* rules whose content had gone
#     stale and wrong; a stateless deploy re-armed those false rules every run.
# ─────────────────────────────────────────────────────────────────────────────
read -r SRC PROJ <<< "$(new_scenario tombstone)"
echo "rule text" > "$SRC/stale.md"

test_start "tombstone: first deploy writes the file"
_pv_begin "$PROJ"; _pv_deploy_file ".claude/rules/stale.md" "$SRC/stale.md" "$PROJ/.claude/rules/stale.md"; _pv_end
assert_content "$PROJ/.claude/rules/stale.md" "rule text" "first deploy failed"

test_start "tombstone: deletion is detected and recorded"
rm -f "$PROJ/.claude/rules/stale.md"
_pv_begin "$PROJ"
_pv_deploy_file ".claude/rules/stale.md" "$SRC/stale.md" "$PROJ/.claude/rules/stale.md"
_pv_end
if [[ ! -e "$PROJ/.claude/rules/stale.md" ]] \
    && grep -q '"\.claude/rules/stale\.md"' "$PROJ/set/.deploy-manifest.json" \
    && python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
sys.exit(0 if '.claude/rules/stale.md' in d.get('tombstones',[]) else 1)
" "$PROJ/set/.deploy-manifest.json"; then
    test_pass
else
    test_fail "deleted file was resurrected or not tombstoned"
fi

test_start "tombstone: a later run still does not resurrect it"
_pv_begin "$PROJ"; _pv_deploy_file ".claude/rules/stale.md" "$SRC/stale.md" "$PROJ/.claude/rules/stale.md"; _pv_end
if [[ ! -e "$PROJ/.claude/rules/stale.md" ]]; then test_pass; else test_fail "resurrected on the third run"; fi

test_start "tombstone: the file leaves 'files' so it cannot be updated back in"
if python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
sys.exit(0 if '.claude/rules/stale.md' not in d.get('files',{}) else 1)
" "$PROJ/set/.deploy-manifest.json"; then
    test_pass
else
    test_fail "tombstoned path still carries a files entry"
fi

test_start "tombstone: clearing the entry restores deployment"
python3 -c "
import json,sys
p=sys.argv[1]
d=json.load(open(p))
d['tombstones']=[]
json.dump(d,open(p,'w'),indent=2)
" "$PROJ/set/.deploy-manifest.json"
_pv_begin "$PROJ"; _pv_deploy_file ".claude/rules/stale.md" "$SRC/stale.md" "$PROJ/.claude/rules/stale.md"; _pv_end
assert_content "$PROJ/.claude/rules/stale.md" "rule text" "clearing the tombstone did not restore deployment"

test_start "tombstone: dry run reports it and records nothing"
read -r SRC PROJ <<< "$(new_scenario tombstone_dry)"
echo "x" > "$SRC/d.md"
_pv_begin "$PROJ"; _pv_deploy_file ".claude/d.md" "$SRC/d.md" "$PROJ/.claude/d.md"; _pv_end
rm -f "$PROJ/.claude/d.md"
DRY_RUN=true
out=$(_pv_begin "$PROJ"; _pv_deploy_file ".claude/d.md" "$SRC/d.md" "$PROJ/.claude/d.md" 2>&1; _pv_end)
DRY_RUN=false
tombs_after=$(python3 -c "
import json,sys
print(len(json.load(open(sys.argv[1])).get('tombstones',[])))
" "$PROJ/set/.deploy-manifest.json")
if [[ "$out" == *"Would skip"* ]] && [[ "$out" == *"deleted by the project"* ]] && [[ "$tombs_after" == "0" ]]; then
    test_pass
else
    test_fail "dry run output='$out' tombstones=$tombs_after (want 0)"
fi

echo
echo "─────────────────────────────────────────"
echo "Tests run: $TESTS_RUN, passed: $TESTS_PASSED, failed: $TESTS_FAILED"
[[ $TESTS_FAILED -eq 0 ]]
