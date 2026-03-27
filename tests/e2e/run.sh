#!/usr/bin/env bash
# E2E bootstrap — create a test run from a scaffold, register with manager, start sentinel.
#
# Usage:
#   ./tests/e2e/run.sh <scaffold>           # e.g. craftbrew, minishop
#   ./tests/e2e/run.sh <scaffold> --no-start  # register only, don't start sentinel
#
# Requires: set-core serve running on port 7400

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SET_CORE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCAFFOLDS_DIR="$SCRIPT_DIR/scaffolds"
E2E_RUNS_DIR="${E2E_RUNS_DIR:-$HOME/.local/share/set-core/e2e-runs}"
MANAGER_URL="${SET_MANAGER_URL:-http://localhost:7400}"
START_SENTINEL=true

# --- Args ---

SCAFFOLD=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-start)
            START_SENTINEL=false
            shift
            ;;
        -h|--help)
            echo "Usage: $(basename "$0") <scaffold> [--no-start]"
            echo "Scaffolds: $(ls "$SCAFFOLDS_DIR" 2>/dev/null | tr '\n' ' ')"
            exit 0
            ;;
        *)
            SCAFFOLD="$1"
            shift
            ;;
    esac
done

if [[ -z "$SCAFFOLD" ]]; then
    echo "Error: scaffold name required" >&2
    echo "Available: $(ls "$SCAFFOLDS_DIR" 2>/dev/null | tr '\n' ' ')" >&2
    exit 1
fi

if [[ ! -d "$SCAFFOLDS_DIR/$SCAFFOLD" ]]; then
    echo "Error: scaffold '$SCAFFOLD' not found in $SCAFFOLDS_DIR" >&2
    echo "Available: $(ls "$SCAFFOLDS_DIR" 2>/dev/null | tr '\n' ' ')" >&2
    exit 1
fi

# --- Manager health check ---

if ! curl -sf "$MANAGER_URL/api/projects" >/dev/null 2>&1; then
    echo "Error: set-core service not running at $MANAGER_URL" >&2
    echo "Start it with: set-core serve" >&2
    exit 1
fi

# --- Auto-increment run name ---

mkdir -p "$E2E_RUNS_DIR"
# Find highest existing run number and increment
RUN_NUM=0
for d in "$E2E_RUNS_DIR/${SCAFFOLD}-run"*; do
    [[ -d "$d" ]] || continue
    n="${d##*-run}"
    [[ "$n" =~ ^[0-9]+$ ]] && (( n > RUN_NUM )) && RUN_NUM=$n
done
RUN_NUM=$((RUN_NUM + 1))
RUN_NAME="${SCAFFOLD}-run${RUN_NUM}"
RUN_DIR="$E2E_RUNS_DIR/$RUN_NAME"

echo "=== E2E Bootstrap: $RUN_NAME ==="
echo "  Scaffold: $SCAFFOLD"
echo "  Run dir:  $RUN_DIR"

# --- Create project directory ---

mkdir -p "$RUN_DIR"
cd "$RUN_DIR"
git init -q

# --- Copy scaffold docs ---

if [[ -d "$SCAFFOLDS_DIR/$SCAFFOLD/docs" ]]; then
    cp -r "$SCAFFOLDS_DIR/$SCAFFOLD/docs" docs/
    echo "  Copied docs/ ($(find docs/ -type f | wc -l) files)"
fi

# Copy any other scaffold files (orchestration.yaml, etc.)
for f in "$SCAFFOLDS_DIR/$SCAFFOLD"/*; do
    fname="$(basename "$f")"
    [[ "$fname" == "docs" ]] && continue
    cp -r "$f" "$fname"
done

# Initial commit so set-project init works
git add -A
git commit -q -m "E2E scaffold: $SCAFFOLD"

# --- set-project init ---

# Read project type and template from scaffold config
PROJECT_TYPE="web"
TEMPLATE=""
if [[ -f "$SCAFFOLDS_DIR/$SCAFFOLD/scaffold.yaml" ]]; then
    PROJECT_TYPE=$(grep '^project_type:' "$SCAFFOLDS_DIR/$SCAFFOLD/scaffold.yaml" | sed 's/^project_type: *//')
    TEMPLATE=$(grep '^template:' "$SCAFFOLDS_DIR/$SCAFFOLD/scaffold.yaml" | sed 's/^template: *//')
fi

INIT_ARGS=(init --name "$RUN_NAME" --project-type "$PROJECT_TYPE")
[[ -n "$TEMPLATE" ]] && INIT_ARGS+=(--template "$TEMPLATE")

echo "  Running set-project init (type=$PROJECT_TYPE, template=${TEMPLATE:-auto})..."
"$SET_CORE_ROOT/bin/set-project" "${INIT_ARGS[@]}" 2>&1 | sed 's/^/    /'

# --- Register with manager ---

echo "  Registering with manager..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X POST "$MANAGER_URL/api/projects" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$RUN_NAME\",\"path\":\"$RUN_DIR\",\"mode\":\"e2e\"}" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" != "201" && "$HTTP_CODE" != "200" ]]; then
    echo "Error: manager registration failed (HTTP $HTTP_CODE)" >&2
    exit 1
fi
echo "  Registered: $RUN_NAME"

# --- Start sentinel ---

if [[ "$START_SENTINEL" == "true" ]]; then
    echo "  Starting sentinel..."
    RESULT=$(curl -sf \
        -X POST "$MANAGER_URL/api/projects/$RUN_NAME/sentinel/start" \
        -H "Content-Type: application/json" \
        -d '{"spec":"docs/"}' 2>/dev/null || echo '{"status":"error"}')
    PID=$(echo "$RESULT" | grep -o '"pid":[0-9]*' | grep -o '[0-9]*' || echo "unknown")
    echo "  Sentinel started (PID: $PID)"
fi

# --- Done ---

echo ""
echo "=== $RUN_NAME ready ==="
echo "  Monitor: $MANAGER_URL/p/$RUN_NAME/orch"
echo "  Dir:     $RUN_DIR"
echo "  Report:  set-e2e-report --project-dir $RUN_DIR"
