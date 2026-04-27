#!/usr/bin/env bash
# Capture screenshots of a v0.app design source rendered in isolation.
#
# Renders the v0-export/ directory's Next.js dev server and screenshots each
# discovered page. Pairs with capture-app-screenshots.sh — together they show
# "design source ↔ built result" in the README and docs/learn pages.
#
# Usage:
#   ./scripts/capture-design-screenshots.sh                      # latest "done" project's v0-export
#   ./scripts/capture-design-screenshots.sh micro-web-run-20260426-2110
#   ./scripts/capture-design-screenshots.sh /path/to/project     # absolute path
#   ./scripts/capture-design-screenshots.sh --v0-dir /path/to/v0-export   # explicit v0-export
#
# Dependencies:
#   - Node.js + pnpm (in the v0-export project)
#   - Playwright chromium (from set-core's web/ package)
#
# Output:
#   docs/images/auto/design/<route>.png

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$ROOT_DIR/docs/images/auto/design"
RUNS_DIR="$HOME/.local/share/set-core/e2e-runs"
PORT=3200

# ── Resolve v0-export directory ──

V0_DIR=""

if [[ "${1:-}" == "--v0-dir" && -n "${2:-}" ]]; then
    V0_DIR="$2"
elif [[ "${1:-}" == /* && -d "$1/v0-export" ]]; then
    V0_DIR="$1/v0-export"
elif [[ -n "${1:-}" && -d "$RUNS_DIR/$1/v0-export" ]]; then
    V0_DIR="$RUNS_DIR/$1/v0-export"
elif [[ -z "${1:-}" ]]; then
    # Auto-discover: latest "done" project with a v0-export/ subdirectory.
    best_dir="" best_time=0
    _state_base="$(python3 -c 'import os, sys; sys.path.insert(0, "lib"); from set_orch.paths import LineagePaths; print(os.path.basename(LineagePaths("/tmp").state_file))' 2>/dev/null || printf 'state.json')"
    for run_dir in "$RUNS_DIR"/*/; do
        [[ -d "$run_dir/v0-export" ]] || continue
        local_state="$run_dir/orchestration-$_state_base"
        if [[ -f "$local_state" ]]; then
            status=$(python3 -c "import json; print(json.load(open('$local_state')).get('status',''))" 2>/dev/null || true)
            [[ "$status" == "done" || "$status" == "accepted" ]] || continue
        fi
        mtime=$(stat -c %Y "$run_dir/v0-export" 2>/dev/null || echo 0)
        if (( mtime > best_time )); then
            best_time=$mtime
            best_dir="$run_dir/v0-export"
        fi
    done
    V0_DIR="${best_dir%/}"
fi

if [[ -z "$V0_DIR" || ! -d "$V0_DIR" ]]; then
    echo "ERROR: No v0-export found." >&2
    echo "  Try: $0 <project-name>  or  $0 --v0-dir /path/to/v0-export" >&2
    echo "  Auto-discovery scans $RUNS_DIR/*/v0-export with status in {done, accepted}." >&2
    exit 1
fi

PROJECT_NAME="$(basename "$(dirname "$V0_DIR")")"

echo "=== v0 Design Source Screenshots ==="
echo "Project: $PROJECT_NAME"
echo "v0-dir:  $V0_DIR"
echo "Output:  $OUT_DIR"
echo ""

if [[ ! -f "$V0_DIR/package.json" ]]; then
    echo "ERROR: No package.json in $V0_DIR — not a Next.js project." >&2
    exit 1
fi

# Clean previous screenshots
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# Install dependencies if needed
if [[ ! -d "$V0_DIR/node_modules" ]]; then
    echo "Installing v0-export dependencies..."
    (cd "$V0_DIR" && pnpm install --prefer-frozen-lockfile 2>/dev/null || pnpm install 2>/dev/null)
    echo ""
fi

# Start dev server
echo "Starting v0-export dev server on port $PORT..."
(cd "$V0_DIR" && pnpm dev --port "$PORT" &>/dev/null) &
SERVER_PID=$!

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]]; then
        # pnpm spawns next-server as a child; killing pnpm alone leaves the
        # listener orphaned holding the port. Kill descendants first.
        pkill -P "$SERVER_PID" 2>/dev/null || true
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

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
    echo "ERROR: Server did not start within 30s" >&2
    exit 1
fi

echo "Server ready."
echo ""

# Capture screenshots
echo "Capturing screenshots..."
(
    cd "$ROOT_DIR/web"
    E2E_DESIGN_URL="http://localhost:${PORT}" \
    V0_EXPORT_DIR="$V0_DIR" \
    npx playwright test --config=playwright.design.config.ts --reporter=list 2>&1
) || echo "  (some screenshots may have failed)"

echo ""
echo "Done. Design screenshots in: $OUT_DIR/"
ls -la "$OUT_DIR"/*.png 2>/dev/null | awk '{print "  " $NF " (" $5 " bytes)"}'
