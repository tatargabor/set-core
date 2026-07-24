#!/usr/bin/env bash
# Tests for the two deploy mutation paths that sit outside both deploy engines.
#
#   1. `_cleanup_deprecated_memory_refs` (lib/project/deploy.sh) — edits .claude files
#      in place. It must only ever touch a file the provenance ledger says set-core
#      deployed and the project has not since changed.
#   2. `set-deploy-hooks`' merge (bin/set-deploy-hooks) — writes settings.json. It must
#      add set-core's hooks WITHOUT displacing the project's, which a jq `*` merge does
#      silently because `*` replaces arrays and every hook event is an array.
#
# Assertions are on file content, never on log text: a regression must not be able to
# pass by printing reassuring words.
#
# Run with: ./tests/unit/test_deploy_mutation_paths.sh

set -uo pipefail

SCRIPT_DIR_TEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_TEST/../.." && pwd)"

source "$PROJECT_DIR/bin/set-common.sh"

SCRIPT_DIR="$PROJECT_DIR/bin"
SET_TOOLS_ROOT="$PROJECT_DIR"
DRY_RUN=false
source "$PROJECT_DIR/lib/project/deploy_provenance.sh"
source "$PROJECT_DIR/lib/project/deploy.sh"

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

test_start() { TESTS_RUN=$((TESTS_RUN + 1)); echo -n "Test $TESTS_RUN: $1 ... "; }
test_pass()  { TESTS_PASSED=$((TESTS_PASSED + 1)); echo -e "${GREEN}PASS${NC}"; }
test_fail()  { TESTS_FAILED=$((TESTS_FAILED + 1)); echo -e "${RED}FAIL${NC}: $1"; }

assert_eq() {
    local actual="$1" expected="$2" msg="$3"
    if [[ "$actual" == "$expected" ]]; then test_pass; else
        test_fail "$msg (expected '$expected', got '$actual')"
    fi
}

assert_grep() {
    local file="$1" pattern="$2" msg="$3"
    if grep -q -- "$pattern" "$file" 2>/dev/null; then test_pass; else
        test_fail "$msg (pattern '$pattern' missing from $file)"
    fi
}

assert_no_grep() {
    local file="$1" pattern="$2" msg="$3"
    if grep -q -- "$pattern" "$file" 2>/dev/null; then
        test_fail "$msg (pattern '$pattern' still present in $file)"
    else test_pass; fi
}

WORK=$(mktemp -d -t set-mut-test.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

# A consumer project with one set-core-deployed command file and one the project wrote.
# The ledger records only the former, with its real hash.
new_cleanup_project() {
    local name="$1"
    local proj="$WORK/$name"
    mkdir -p "$proj/.claude/commands/docs" "$proj/.claude/commands/set" "$proj/.claude/skills/openspec-ff-change" "$proj/set"

    printf 'Deployed by set-core.\nRun: set-memory recall "$TOPIC"\nMore text.\n' \
        > "$proj/.claude/commands/docs/ingest.md"
    printf 'Hand written by the project.\nRun: set-memory remember "note"\nKeep me.\n' \
        > "$proj/.claude/commands/docs/handmade.md"
    printf 'set-core own command.\nset-memory recall "x"\n' \
        > "$proj/.claude/commands/set/status.md"

    local deployed_hash
    deployed_hash=$(_pv_sha256 "$proj/.claude/commands/docs/ingest.md")
    cat > "$proj/set/.deploy-manifest.json" << LEDGER
{
  "version": 2,
  "files": { ".claude/commands/docs/ingest.md": "$deployed_hash" },
  "tombstones": []
}
LEDGER
    echo "$proj"
}

# ─────────────────────────────────────────────────────────────────────────────
# Path 1 — the deprecated-memory cleanup
# ─────────────────────────────────────────────────────────────────────────────

PROJ=$(new_cleanup_project owned)
_cleanup_deprecated_memory_refs "$PROJ" >/dev/null 2>&1

test_start "cleanup: edits a file set-core deployed and the project left alone"
assert_no_grep "$PROJ/.claude/commands/docs/ingest.md" 'set-memory recall' \
    "the deprecated line should be gone from a set-core-owned file"

test_start "cleanup: keeps the surrounding content of that file"
assert_grep "$PROJ/.claude/commands/docs/ingest.md" 'More text.' \
    "only the matching line may be removed"

test_start "cleanup: NEVER touches a project-authored file"
assert_grep "$PROJ/.claude/commands/docs/handmade.md" 'set-memory remember' \
    "a file absent from the ledger belongs to the project"

test_start "cleanup: skips commands/set/ by intent"
assert_grep "$PROJ/.claude/commands/set/status.md" 'set-memory recall' \
    "set-core's own commands use set-memory deliberately"

test_start "cleanup: rewrites the ledger hash after its own edit"
NEW_HASH=$(_pv_sha256 "$PROJ/.claude/commands/docs/ingest.md")
LEDGER_HASH=$(python3 -c "
import json,sys
print(json.load(open(sys.argv[1]))['files'].get('.claude/commands/docs/ingest.md',''))
" "$PROJ/set/.deploy-manifest.json")
assert_eq "$LEDGER_HASH" "$NEW_HASH" \
    "without this the next deploy reads its own edit as a project change and skips forever"

# A file that WAS deployed but the project has since edited must be left alone.
PROJ=$(new_cleanup_project edited)
printf 'Deployed by set-core.\nRun: set-memory recall "$TOPIC"\nPROJECT EDIT.\n' \
    > "$PROJ/.claude/commands/docs/ingest.md"
_cleanup_deprecated_memory_refs "$PROJ" >/dev/null 2>&1

test_start "cleanup: leaves a ledger file the project has since modified"
assert_grep "$PROJ/.claude/commands/docs/ingest.md" 'set-memory recall' \
    "a changed hash means the project owns the file now"

# Dry run must report and write nothing.
PROJ=$(new_cleanup_project dryrun)
BEFORE=$(_pv_sha256 "$PROJ/.claude/commands/docs/ingest.md")
DRY_RUN=true
_cleanup_deprecated_memory_refs "$PROJ" >/dev/null 2>&1
DRY_RUN=false

test_start "cleanup: --dry-run leaves the file byte-identical"
assert_eq "$(_pv_sha256 "$PROJ/.claude/commands/docs/ingest.md")" "$BEFORE" \
    "a dry run must not write"

test_start "cleanup: --dry-run does not delete hot-topics.json"
PROJ=$(new_cleanup_project dryhot)
echo '{}' > "$PROJ/.claude/hot-topics.json"
DRY_RUN=true
_cleanup_deprecated_memory_refs "$PROJ" >/dev/null 2>&1
DRY_RUN=false
if [[ -f "$PROJ/.claude/hot-topics.json" ]]; then test_pass; else
    test_fail "a dry run must not delete files"
fi

test_start "cleanup: a real run does delete hot-topics.json"
_cleanup_deprecated_memory_refs "$PROJ" >/dev/null 2>&1
if [[ ! -f "$PROJ/.claude/hot-topics.json" ]]; then test_pass; else
    test_fail "set-core's own superseded cache should go"
fi

# SKILL.md hook blocks follow the same ownership rule.
PROJ=$(new_cleanup_project skills)
SK="$PROJ/.claude/skills/openspec-ff-change/SKILL.md"
printf 'Header\n<!-- set-memory hooks -->\nrecall stuff\n<!-- /set-memory hooks -->\nFooter\n' > "$SK"
SKP="$PROJ/.claude/skills/project-own/SKILL.md"
mkdir -p "$(dirname "$SKP")"
printf 'Mine\n<!-- set-memory hooks -->\nrecall stuff\n<!-- /set-memory hooks -->\nEnd\n' > "$SKP"
SK_HASH=$(_pv_sha256 "$SK")
python3 -c "
import json,sys
p=sys.argv[1]
d=json.load(open(p))
d['files']['.claude/skills/openspec-ff-change/SKILL.md']=sys.argv[2]
json.dump(d,open(p,'w'))
" "$PROJ/set/.deploy-manifest.json" "$SK_HASH"
_cleanup_deprecated_memory_refs "$PROJ" >/dev/null 2>&1

test_start "cleanup: strips a hook block from a set-core-deployed SKILL.md"
assert_no_grep "$SK" 'set-memory hooks' "the block should be gone"

test_start "cleanup: leaves a project-authored SKILL.md alone"
assert_grep "$SKP" 'set-memory hooks' "not in the ledger — not ours"

# ─────────────────────────────────────────────────────────────────────────────
# Path 2 — the settings.json hook merge
# ─────────────────────────────────────────────────────────────────────────────

# A consumer config carrying its own hooks, deliberately NOT canonical (no
# SubagentStart/SubagentStop) so the merge branch actually runs.
new_hooks_project() {
    local name="$1"
    local proj="$WORK/$name"
    mkdir -p "$proj/.claude"
    cat > "$proj/.claude/settings.json" << 'SETTINGS'
{
  "permissions": {"allow": ["Bash(git status)"]},
  "hooks": {
    "SessionStart": [
      {"matcher": "", "hooks": [
        {"type": "command", "command": "set-hook-memory SessionStart", "timeout": 10},
        {"type": "command", "command": "bash scripts/hooks/worktree-env-check.sh", "timeout": 15}
      ]}
    ],
    "InstructionsLoaded": [
      {"matcher": "", "hooks": [{"type": "command", "command": "bash scripts/hooks/instructions-log.sh"}]}
    ],
    "PreToolUse": [
      {"matcher": "Skill", "hooks": [{"type": "command", "command": "set-hook-activity", "timeout": 5}]},
      {"matcher": "Bash", "hooks": [
        {"type": "command", "command": "bash scripts/hooks/font-protect.sh"},
        {"type": "command", "command": "python3 scripts/hooks/bash-damage-control.py"}
      ]}
    ],
    "PostToolUse": [
      {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "bash scripts/hooks/domain-brief.sh"}]}
    ],
    "Stop": [
      {"matcher": "", "hooks": [{"type": "command", "command": "set-hook-stop", "timeout": 5}]}
    ]
  }
}
SETTINGS
    echo "$proj"
}

count_project_hooks() {
    jq '[.hooks[][] | .hooks[] | select(.command | startswith("set-hook") | not)] | length' \
        "$1/.claude/settings.json" 2>/dev/null || echo -1
}

PROJ=$(new_hooks_project merge)
BEFORE_COUNT=$(count_project_hooks "$PROJ")
"$PROJECT_DIR/bin/set-deploy-hooks" --quiet "$PROJ" >/dev/null 2>&1
AFTER_COUNT=$(count_project_hooks "$PROJ")

test_start "hooks: every project hook survives the merge"
assert_eq "$AFTER_COUNT" "$BEFORE_COUNT" \
    "the jq '*' merge replaced whole event arrays; this is the regression that matters"

test_start "hooks: the PreToolUse security firewall specifically survives"
if jq -e '.hooks.PreToolUse[] | select(.matcher=="Bash") | .hooks[]
          | select(.command | test("bash-damage-control"))' \
        "$PROJ/.claude/settings.json" >/dev/null 2>&1; then test_pass; else
    test_fail "a consumer's destructive-command firewall was dropped"
fi

test_start "hooks: a project-only event is untouched"
if jq -e '.hooks.InstructionsLoaded[0].hooks[0].command' \
        "$PROJ/.claude/settings.json" >/dev/null 2>&1; then test_pass; else
    test_fail "events set-core does not ship must be left alone"
fi

test_start "hooks: set-core's own hooks are actually deployed"
SETCORE_COUNT=$(jq '[.hooks[][] | .hooks[] | select(.command | startswith("set-hook"))] | length' \
    "$PROJ/.claude/settings.json")
if [[ "$SETCORE_COUNT" -ge 10 ]]; then test_pass; else
    test_fail "expected the full hook set, got $SETCORE_COUNT"
fi

test_start "hooks: order inside a shared matcher is preserved"
assert_eq "$(jq -r '.hooks.SessionStart[0].hooks[1].command' "$PROJ/.claude/settings.json")" \
    "bash scripts/hooks/worktree-env-check.sh" \
    "an existing command is updated in place, not appended after"

test_start "hooks: non-hook settings survive"
assert_eq "$(jq -c '.permissions.allow' "$PROJ/.claude/settings.json")" '["Bash(git status)"]' \
    "the merge must not disturb the rest of settings.json"

test_start "hooks: a backup is written before modification"
if [[ -f "$PROJ/.claude/settings.json.bak" ]]; then test_pass; else
    test_fail "the .bak safety net is required"
fi

test_start "hooks: re-running is idempotent"
TOTAL_1=$(jq '[.hooks[][] | .hooks[]] | length' "$PROJ/.claude/settings.json")
"$PROJECT_DIR/bin/set-deploy-hooks" --quiet "$PROJ" >/dev/null 2>&1
TOTAL_2=$(jq '[.hooks[][] | .hooks[]] | length' "$PROJ/.claude/settings.json")
assert_eq "$TOTAL_2" "$TOTAL_1" "a second run must not duplicate hooks"

# Upgrade path: legacy individual memory scripts are retired, project hooks are not.
PROJ=$(new_hooks_project upgrade)
python3 -c "
import json,sys
p=sys.argv[1]+'/.claude/settings.json'
d=json.load(open(p))
d['hooks']['SessionStart'][0]['hooks'].append(
    {'type':'command','command':'set-hook-memory-warmstart','timeout':10})
json.dump(d,open(p,'w'),indent=2)
" "$PROJ"
BEFORE_COUNT=$(count_project_hooks "$PROJ")
"$PROJECT_DIR/bin/set-deploy-hooks" --quiet "$PROJ" >/dev/null 2>&1

test_start "hooks/upgrade: the legacy individual script is retired"
assert_no_grep "$PROJ/.claude/settings.json" 'set-hook-memory-warmstart' \
    "that is the whole point of the upgrade branch"

test_start "hooks/upgrade: project hooks still survive"
assert_eq "$(count_project_hooks "$PROJ")" "$BEFORE_COUNT" \
    "the upgrade branch dropped whole event arrays too"

# --no-memory strips set-core's memory hooks but not the project's.
PROJ=$(new_hooks_project nomemory)
BEFORE_COUNT=$(count_project_hooks "$PROJ")
"$PROJECT_DIR/bin/set-deploy-hooks" --quiet --no-memory "$PROJ" >/dev/null 2>&1

test_start "hooks/--no-memory: set-core memory hooks are removed"
assert_no_grep "$PROJ/.claude/settings.json" 'set-hook-memory' \
    "--no-memory must still mean no memory hooks"

test_start "hooks/--no-memory: project hooks are NOT removed"
assert_eq "$(count_project_hooks "$PROJ")" "$BEFORE_COUNT" \
    "stripping set-core's hooks must not strip the project's"

# A settings.json with no hooks key at all must still gain them.
PROJ="$WORK/nohooks"
mkdir -p "$PROJ/.claude"
echo '{"permissions":{"allow":[]}}' > "$PROJ/.claude/settings.json"
"$PROJECT_DIR/bin/set-deploy-hooks" --quiet "$PROJ" >/dev/null 2>&1

test_start "hooks: a config with no hooks key gains the full set"
SETCORE_COUNT=$(jq '[.hooks[][] | .hooks[] | select(.command | startswith("set-hook"))] | length' \
    "$PROJ/.claude/settings.json" 2>/dev/null || echo 0)
if [[ "$SETCORE_COUNT" -ge 10 ]]; then test_pass; else
    test_fail "expected the full hook set, got $SETCORE_COUNT"
fi

echo
echo "─────────────────────────────────────────"
echo "Tests run: $TESTS_RUN, passed: $TESTS_PASSED, failed: $TESTS_FAILED"
[[ $TESTS_FAILED -eq 0 ]]
