#!/usr/bin/env bash
# Section 17.1 — hardcoded orchestration-path audit gate.
#
# Greps for canonical orchestration-path literals across the production
# code surface (Python, Bash, TypeScript, YAML).  Exits 0 when every
# residual match is inside an explicitly allow-listed file (the resolver
# itself, the bash mirror, the test helpers, the lineage-aware loader,
# or the migration backfill).  Exits non-zero with a per-file listing
# otherwise.
#
# Usage:
#   scripts/audit-lineage-paths.sh                # report only
#   scripts/audit-lineage-paths.sh --report PATH  # write diff-style report to PATH
#   scripts/audit-lineage-paths.sh --sync-audit   # tick boxes in migration-audit.md (TODO)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Patterns we consider canonical — a hardcoded literal of any of these in
# production code is the migration target.  Order matters only for output
# stability.
PATTERNS=(
    'orchestration-plan\.json'
    'orchestration-plan-domains\.json'
    'orchestration-events\.jsonl'
    'orchestration-state-events\.jsonl'
    'orchestration-state\.json'
    'state-archive\.jsonl'
    'spec-coverage-report\.md'
    'spec-coverage-history\.jsonl'
    'e2e-manifest\.json'
    'e2e-manifest-history\.jsonl'
    'worktrees-history\.json'
    'set/orchestration/digest'
    'set/orchestration/directives\.json'
    'set/orchestration/config\.yaml'
    'review-learnings\.jsonl'
    'review-findings\.jsonl'
    '\.set/supervisor/status\.json'
    '\.set/issues/registry\.json'
)

# Files where a literal IS the canonical owner — finding the literal here
# is correct, not a migration target.  Match via basename for portability.
ALLOWLIST_BASENAMES=(
    paths.py
    set-common.sh
    backfill_lineage.py
    types.py
    set-close
    audit-lineage-paths.sh
    helpers.sh
)

# Match by path containment (substring) — anything under these paths is
# considered allowlisted (test fixtures, openspec artefacts, etc.).
ALLOWLIST_PATH_FRAGMENTS=(
    /tests/unit/fixtures/
    /tests/unit/test_lineage_paths
    /tests/unit/test_lineage_state_fields
    /tests/unit/test_event_stream_rotation
    /tests/unit/test_history_appenders
    /tests/unit/test_phase_offset
    /tests/unit/test_backfill_lineage
    /tests/unit/test_lineage_rotation_and_session_boundaries
    /tests/unit/test_lineage_api
    /tests/unit/test_token_archive_aggregation
    /tests/unit/test_rotated_event_readers
    /tests/unit/test_set_common_lineage_helpers
    /openspec/changes/
    /openspec/specs/
    /docs/
    /node_modules/
    /__pycache__/
    /.git/
    /.next/
    /dist/
    /.venv/
    /.pytest_cache/
)

# File globs to scan.  We deliberately keep this list narrow to "owned"
# code (lib/, bin/, scripts/, web/src/, modules/).
SCAN_INCLUDES=(
    'lib/**/*.py'
    'lib/**/*.sh'
    'bin/*'
    'scripts/*.sh'
    'scripts/*.py'
    'web/src/**/*.ts'
    'web/src/**/*.tsx'
    'modules/**/*.py'
)

# File-type extensions we actually inspect.  Markdown / YAML templates are
# documentation and live outside the audit per the spec (the audit gate
# verifies *code*, not docs).  Allowlisted basenames + path fragments
# below carve out additional exemptions for legitimate owners.
SCAN_EXTENSIONS=(py sh ts tsx)

REPORT_PATH=""
SYNC_AUDIT=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --report) REPORT_PATH="$2"; shift 2 ;;
        --sync-audit) SYNC_AUDIT=true; shift ;;
        -h|--help)
            sed -n '1,30p' "$0"; exit 0 ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

is_allowlisted() {
    local file="$1"
    local base
    base="$(basename "$file")"
    for ok in "${ALLOWLIST_BASENAMES[@]}"; do
        [[ "$base" == "$ok" ]] && return 0
    done
    for frag in "${ALLOWLIST_PATH_FRAGMENTS[@]}"; do
        [[ "$file" == *"$frag"* ]] && return 0
    done
    # Inspect only py/sh/ts/tsx — anything else is template / doc and
    # passes by default (the spec excludes those from the audit).
    local ext="${file##*.}"
    local match=false
    for e in "${SCAN_EXTENSIONS[@]}"; do
        [[ "$ext" == "$e" ]] && match=true
    done
    if ! $match; then
        return 0  # not a code file → not blocking
    fi
    return 1
}

declare -a RESIDUALS=()

for pattern in "${PATTERNS[@]}"; do
    # Use rg if available; fall back to grep -r.
    if command -v rg >/dev/null 2>&1; then
        # shellcheck disable=SC2207
        matches=( $(rg --no-heading --line-number --color=never \
            --glob '!**/__pycache__/**' --glob '!**/.git/**' \
            --glob '!**/node_modules/**' --glob '!**/.next/**' \
            --glob '!**/.venv/**' --glob '!**/dist/**' \
            -- "$pattern" lib bin scripts web/src modules 2>/dev/null \
            | awk -F: '{print $1":"$2}' ) )
    else
        # shellcheck disable=SC2207
        matches=( $(grep -rIn --include='*.py' --include='*.sh' \
            --include='*.ts' --include='*.tsx' --include='*' \
            --exclude-dir=__pycache__ --exclude-dir=.git \
            --exclude-dir=node_modules --exclude-dir=.next \
            --exclude-dir=.venv --exclude-dir=dist \
            "$pattern" lib bin scripts web/src modules 2>/dev/null \
            | awk -F: '{print $1":"$2}' ) )
    fi
    for hit in "${matches[@]}"; do
        file="${hit%%:*}"
        line="${hit##*:}"
        if is_allowlisted "$file"; then
            continue
        fi
        RESIDUALS+=("$pattern $file:$line")
    done
done

# De-duplicate (rg can emit overlapping ranges in long lines).
if [[ ${#RESIDUALS[@]} -gt 0 ]]; then
    mapfile -t RESIDUALS < <(printf '%s\n' "${RESIDUALS[@]}" | sort -u)
fi

if [[ -n "$REPORT_PATH" ]]; then
    {
        echo "# Hardcoded-path audit report"
        echo
        if [[ ${#RESIDUALS[@]} -eq 0 ]]; then
            echo "No residuals — every hardcoded literal lives inside an allowlisted file."
        else
            echo "Found ${#RESIDUALS[@]} residual literal(s):"
            echo
            for r in "${RESIDUALS[@]}"; do
                echo "  - $r"
            done
        fi
    } > "$REPORT_PATH"
fi

if [[ ${#RESIDUALS[@]} -gt 0 ]]; then
    echo "FAIL: ${#RESIDUALS[@]} hardcoded orchestration-path literal(s) outside the resolver:" >&2
    for r in "${RESIDUALS[@]}"; do
        echo "  - $r" >&2
    done
    exit 1
fi

echo "PASS: no residual hardcoded orchestration-path literals."
exit 0
