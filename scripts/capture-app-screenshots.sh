#!/usr/bin/env bash
# Capture screenshots of a consumer app built by orchestration.
#
# Auto-discovers Next.js routes, starts dev server, takes Playwright screenshots.
#
# Usage:
#   ./scripts/capture-app-screenshots.sh                          # latest "done" project
#   ./scripts/capture-app-screenshots.sh minishop-run10           # specific run
#   ./scripts/capture-app-screenshots.sh /path/to/project         # absolute path
#
# Dependencies:
#   - Node.js + pnpm (in the consumer project)
#   - Playwright chromium (from set-core's web/ package)
#   - npx tsx (for running the capture script)
#
# Output:
#   docs/images/auto/app/<name>.png

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$ROOT_DIR/docs/images/auto/app"
RUNS_DIR="$HOME/.local/share/set-core/e2e-runs"
CAPTURE_SCRIPT="$ROOT_DIR/tests/e2e/assets/capture-screenshots.ts"
PORT=3100

# ── Resolve project directory ──

resolve_project() {
    local input="${1:-}"

    # No argument: find latest "done" project via API or filesystem
    if [[ -z "$input" ]]; then
        # Try API first
        local latest
        latest=$(curl -sf http://localhost:7400/api/projects 2>/dev/null \
            | python3 -c "
import sys, json
projects = json.load(sys.stdin)
done = [p for p in projects if p.get('status') == 'done' and p.get('changes_merged', 0) > 0]
done.sort(key=lambda p: p.get('last_updated', ''), reverse=True)
if done: print(done[0]['path'])
" 2>/dev/null || true)

        if [[ -n "$latest" && -d "$latest" ]]; then
            echo "$latest"
            return
        fi

        # Fallback: scan filesystem for latest state.json with status=done
        local best_dir="" best_time=0
        for run_dir in "$RUNS_DIR"/*/; do
            local state="$run_dir/orchestration-state.json"
            [[ -f "$state" ]] || continue
            local status
            status=$(python3 -c "import json; print(json.load(open('$state')).get('status',''))" 2>/dev/null || true)
            [[ "$status" == "done" ]] || continue
            local mtime
            mtime=$(stat -c %Y "$state" 2>/dev/null || echo 0)
            if (( mtime > best_time )); then
                best_time=$mtime
                best_dir="$run_dir"
            fi
        done

        if [[ -n "$best_dir" ]]; then
            echo "${best_dir%/}"
            return
        fi

        echo "ERROR: No 'done' project found. Specify a project name or path." >&2
        return 1
    fi

    # Absolute path
    if [[ "$input" == /* && -d "$input" ]]; then
        echo "$input"
        return
    fi

    # Run name (e.g., minishop-run10)
    if [[ -d "$RUNS_DIR/$input" ]]; then
        echo "$RUNS_DIR/$input"
        return
    fi

    echo "ERROR: Project not found: $input" >&2
    echo "  Checked: $RUNS_DIR/$input" >&2
    return 1
}

# ── Main ──

PROJECT_DIR=$(resolve_project "${1:-}")
PROJECT_NAME=$(basename "$PROJECT_DIR")

echo "=== Consumer App Screenshots ==="
echo "Project: $PROJECT_NAME"
echo "Path:    $PROJECT_DIR"
echo "Output:  $OUT_DIR"
echo ""

# Check for package.json
if [[ ! -f "$PROJECT_DIR/package.json" ]]; then
    echo "ERROR: No package.json found in $PROJECT_DIR"
    exit 1
fi

mkdir -p "$OUT_DIR"

# ── Prisma setup (if applicable) ──

if [[ -d "$PROJECT_DIR/prisma" ]]; then
    echo "Setting up Prisma..."
    (
        cd "$PROJECT_DIR"
        npx prisma generate 2>/dev/null || true
        npx prisma db push --force-reset --accept-data-loss 2>/dev/null || true
        npx prisma db seed 2>/dev/null || echo "  (no seed script, skipping)"
    )
    echo ""
fi

# ── Install dependencies ──

if [[ ! -d "$PROJECT_DIR/node_modules" ]]; then
    echo "Installing dependencies..."
    (cd "$PROJECT_DIR" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install 2>/dev/null)
    echo ""
fi

# ── Start dev server ──

echo "Starting dev server on port $PORT..."
(cd "$PROJECT_DIR" && pnpm dev --port "$PORT" &>/dev/null) &
SERVER_PID=$!

# Wait for server
RETRIES=30
echo -n "Waiting for server"
while (( RETRIES > 0 )); do
    if curl -sf -o /dev/null "http://localhost:${PORT}/" 2>/dev/null; then
        break
    fi
    echo -n "."
    sleep 1
    ((RETRIES--)) || true
done
echo ""

if (( RETRIES == 0 )); then
    echo "ERROR: Server did not start within 30s"
    kill "$SERVER_PID" 2>/dev/null || true
    exit 1
fi

echo "Server ready."
echo ""

# ── Capture screenshots ──

echo "Capturing screenshots..."
# Run as Playwright test with app-specific config (no E2E_PROJECT required)
(
    cd "$ROOT_DIR/web"
    E2E_APP_URL="http://localhost:${PORT}" \
    PROJECT_DIR="$PROJECT_DIR" \
    npx playwright test --config=playwright.app.config.ts --reporter=list 2>&1
) || echo "  (some screenshots may have failed)"

# ── Cleanup ──

echo ""
echo "Stopping dev server..."
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true

echo ""
echo "Done. App screenshots in: $OUT_DIR/"
ls -la "$OUT_DIR/"*.png 2>/dev/null | awk '{print "  " $NF " (" $5 " bytes)"}'
