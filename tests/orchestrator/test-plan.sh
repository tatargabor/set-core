#!/usr/bin/env bash
# Level 2 Integration test: plan generation via Claude
# Requires: Claude CLI available, costs ~5-10k tokens
# Run with: ./tests/orchestrator/test-plan.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

source "$PROJECT_DIR/bin/set-common.sh"

# ============================================================
# Setup: temp project with sample brief
# ============================================================

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

info "Setting up test project in $TMPDIR..."

cd "$TMPDIR"
git init -q
mkdir -p openspec/specs openspec/changes

# Copy sample brief
cp "$SCRIPT_DIR/sample-brief.md" openspec/project-brief.md

# Create a dummy spec to test context collection
mkdir -p openspec/specs/dummy-spec
echo "# Dummy Spec" > openspec/specs/dummy-spec/spec.md

git add -A && git commit -q -m "init"

# ============================================================
# Test: set-orchestrate plan
# ============================================================

info "Running set-orchestrate plan..."

"$PROJECT_DIR/bin/set-orchestrate" plan 2>&1 || {
    error "set-orchestrate plan failed"
    exit 1
}

# Validate plan file exists
if [[ ! -f orchestration-plan.json ]]; then
    error "orchestration-plan.json not created"
    exit 1
fi
success "Plan file created"

# Validate JSON structure
if ! jq empty orchestration-plan.json 2>/dev/null; then
    error "Plan is not valid JSON"
    exit 1
fi
success "Plan is valid JSON"

# Validate required fields
for field in plan_version brief_hash created_at changes; do
    val=$(jq -r ".$field // empty" orchestration-plan.json)
    if [[ -z "$val" ]]; then
        error "Missing field: $field"
        exit 1
    fi
done
success "All required fields present"

# Validate changes array
change_count=$(jq '.changes | length' orchestration-plan.json)
if [[ "$change_count" -lt 1 ]]; then
    error "No changes in plan (expected >= 1)"
    exit 1
fi
info "Plan has $change_count changes"

# Validate change names are kebab-case
bad_names=$(jq -r '.changes[].name' orchestration-plan.json | grep -vE '^[a-z][a-z0-9-]*$' || true)
if [[ -n "$bad_names" ]]; then
    error "Non-kebab-case names found: $bad_names"
    exit 1
fi
success "All change names are kebab-case"

# Validate depends_on references exist
all_names=$(jq -r '.changes[].name' orchestration-plan.json | sort)
all_deps=$(jq -r '.changes[].depends_on[]?' orchestration-plan.json 2>/dev/null | sort -u || true)
if [[ -n "$all_deps" ]]; then
    missing=$(comm -23 <(echo "$all_deps") <(echo "$all_names") || true)
    if [[ -n "$missing" ]]; then
        error "Dangling dependency references: $missing"
        exit 1
    fi
fi
success "All dependency references are valid"

# Validate no circular dependencies (topological sort succeeds)
if ! "$PROJECT_DIR/bin/set-orchestrate" plan --show &>/dev/null; then
    error "Plan has circular dependencies"
    exit 1
fi
success "No circular dependencies"

# Validate each change has required fields
for i in $(seq 0 $((change_count - 1))); do
    name=$(jq -r ".changes[$i].name" orchestration-plan.json)
    scope=$(jq -r ".changes[$i].scope // empty" orchestration-plan.json)
    if [[ -z "$scope" ]]; then
        error "Change '$name' missing scope"
        exit 1
    fi
done
success "All changes have scope"

# Show plan
echo ""
info "=== Generated Plan ==="
jq -r '.changes[] | "  \(.name) [\(.complexity // "?")] deps=\(.depends_on | join(",") | if . == "" then "none" else . end)"' orchestration-plan.json
echo ""

# Validate plan_version
pv=$(jq -r '.plan_version' orchestration-plan.json)
if [[ "$pv" -ge 1 ]]; then
    success "Plan version: $pv"
else
    error "Invalid plan version: $pv"
    exit 1
fi

# Validate brief_hash is present and non-empty
bh=$(jq -r '.brief_hash' orchestration-plan.json)
if [[ -n "$bh" && "$bh" != "null" && "$bh" != "unknown" ]]; then
    success "Brief hash recorded: ${bh:0:16}..."
else
    error "Missing or invalid brief hash: $bh"
    exit 1
fi

echo ""
success "All Level 2 integration tests passed ($change_count changes generated)"
