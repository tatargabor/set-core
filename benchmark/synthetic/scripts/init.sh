#!/bin/bash
# init.sh — Bootstrap a MemoryProbe benchmark run
# Usage: ./init.sh --mode a|b|c --target <dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Parse args ---
MODE=""
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$MODE" ]] || [[ -z "$TARGET" ]]; then
  echo "Usage: ./init.sh --mode a|b|c|d --target <dir>"
  echo ""
  echo "Modes:"
  echo "  a  Baseline (no memory)"
  echo "  b  Full memory (save + recall)"
  echo "  c  Pre-seeded (recall only, skip C01-C02)"
  echo "  d  Rules (deterministic .claude/rules.yaml, skip C01-C02)"
  exit 1
fi

if [[ "$MODE" != "a" && "$MODE" != "b" && "$MODE" != "c" && "$MODE" != "d" ]]; then
  echo "Error: mode must be a, b, c, or d"
  exit 1
fi

# --- Prerequisites ---
echo "Checking prerequisites..."

command -v node >/dev/null || { echo "Error: node not found"; exit 1; }
command -v npm >/dev/null || { echo "Error: npm not found"; exit 1; }
command -v claude >/dev/null || { echo "Error: claude CLI not found"; exit 1; }

if [[ "$MODE" == "b" || "$MODE" == "c" ]]; then
  command -v set-memory >/dev/null || { echo "Error: set-memory not found (required for mode $MODE)"; exit 1; }
fi

if [[ "$MODE" == "d" ]]; then
  command -v set-memory >/dev/null || { echo "Error: set-memory not found (required for mode d — hook injection)"; exit 1; }
fi

# --- Check target ---
if [[ -d "$TARGET" ]]; then
  echo "Error: $TARGET already exists. Remove it first or use a different path."
  exit 1
fi

echo "Mode: $MODE"
echo "Target: $TARGET"
echo ""

# --- Create project ---
mkdir -p "$TARGET"
cd "$TARGET"

git init
npm init -y > /dev/null 2>&1
npm install express better-sqlite3 nanoid@3 > /dev/null 2>&1

# --- Create directories ---
mkdir -p src/{routes,db,lib,middleware} data docs/changes tests results

# --- Copy project spec ---
cp "$BENCH_DIR/project-spec.md" docs/project-spec.md

# --- Copy change files (strip evaluator notes) ---
for f in "$BENCH_DIR"/changes/*.md; do
  BASENAME="$(basename "$f")"
  sed '/<!-- EVALUATOR NOTES BELOW/,$d' "$f" > "docs/changes/$BASENAME"
done

# --- Copy test scripts ---
cp "$BENCH_DIR"/tests/test-*.sh tests/

# --- Deploy CLAUDE.md ---
if [[ "$MODE" == "a" ]]; then
  cp "$BENCH_DIR/claude-md/baseline.md" CLAUDE.md
elif [[ "$MODE" == "d" ]]; then
  cp "$BENCH_DIR/claude-md/with-rules.md" CLAUDE.md
else
  cp "$BENCH_DIR/claude-md/with-memory.md" CLAUDE.md
fi

# --- Verify no evaluator notes leaked ---
if grep -rq "EVALUATOR NOTES" docs/changes/; then
  echo "FATAL: Evaluator notes leaked into agent-visible files!"
  exit 1
fi

# --- Set port in CLAUDE.md based on mode ---
if [[ "$MODE" == "a" ]]; then
  PORT=4000
elif [[ "$MODE" == "d" ]]; then
  PORT=4002
else
  PORT=4001
fi

# --- Enable metrics collection (all modes with hooks) ---
if [[ "$MODE" == "b" || "$MODE" == "c" || "$MODE" == "d" ]]; then
  mkdir -p "$HOME/.local/share/set-core/metrics"
  touch "$HOME/.local/share/set-core/metrics/.enabled"
fi

# --- Mode-specific setup ---
if [[ "$MODE" == "b" ]]; then
  echo "Setting up memory hooks..."
  if command -v set-deploy-hooks >/dev/null 2>&1; then
    set-deploy-hooks . 2>/dev/null || true
  fi
fi

if [[ "$MODE" == "c" ]]; then
  echo "Pre-seeding convention memories and deploying hooks..."
  bash "$BENCH_DIR/scripts/pre-seed.sh"
  if command -v set-deploy-hooks >/dev/null 2>&1; then
    set-deploy-hooks . 2>/dev/null || true
  fi
fi

if [[ "$MODE" == "d" ]]; then
  echo "Deploying rules.yaml and memory hooks..."
  bash "$BENCH_DIR/scripts/pre-rules.sh"
  if command -v set-deploy-hooks >/dev/null 2>&1; then
    set-deploy-hooks . 2>/dev/null || true
  fi
fi

# --- Initial commit ---
git add -A
git commit -m "MemoryProbe: initial setup (mode $MODE)" > /dev/null

# --- Summary ---
echo ""
echo "=== MemoryProbe initialized ==="
echo "  Mode:   $MODE"
echo "  Target: $TARGET"
echo "  Port:   $PORT"
echo ""
echo "Next steps:"

if [[ "$MODE" == "c" || "$MODE" == "d" ]]; then
  echo "  1. cd $TARGET"
  echo "  2. bash $BENCH_DIR/scripts/run.sh . --start 3 --end 5"
else
  echo "  1. cd $TARGET"
  echo "  2. bash $BENCH_DIR/scripts/run.sh ."
fi

echo ""
echo "Or run manually:"
if [[ "$MODE" == "c" || "$MODE" == "d" ]]; then
  echo "  claude --dangerously-skip-permissions -p \"Implement docs/changes/03-comments-activity.md\" --max-turns 25"
else
  echo "  claude --dangerously-skip-permissions -p \"Implement docs/changes/01-event-crud.md\" --max-turns 25"
fi
