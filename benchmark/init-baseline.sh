#!/usr/bin/env bash
# init-baseline.sh - Bootstrap CraftBazaar for Run A (no memory)
#
# Usage: ./init-baseline.sh [target-dir]
# Default target: ~/benchmark/run-a/craftbazaar

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WT_ROOT="$(dirname "$SCRIPT_DIR")"
TARGET="${1:-$HOME/benchmark/run-a/craftbazaar-baseline}"

# --- Prerequisites ---
missing=()
command -v git >/dev/null || missing+=("git")
command -v node >/dev/null || missing+=("node")
command -v openspec >/dev/null || missing+=("openspec (npm i -g @fission-ai/openspec@1.1.1)")
command -v set-deploy-hooks >/dev/null || missing+=("set-deploy-hooks")
if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: Missing prerequisites: ${missing[*]}" >&2
  exit 1
fi

# --- Check target ---
if [ -d "$TARGET/.git" ]; then
  echo "ERROR: $TARGET already has a git repo. Remove it first or pick a different directory." >&2
  exit 1
fi

echo "=== CraftBazaar Benchmark — Run A (Baseline) ==="
echo "Target: $TARGET"
echo ""

# --- Create and init ---
mkdir -p "$TARGET"
cd "$TARGET"

git init
npm init -y --silent

openspec init --tools claude

# openspec init skips config in non-interactive mode — create it
echo "schema: spec-driven" > openspec/config.yaml

set-deploy-hooks --no-memory .

# --- Enable metrics collection ---
mkdir -p "$HOME/.local/share/set-core/metrics"
touch "$HOME/.local/share/set-core/metrics/.enabled"

# --- Directories ---
mkdir -p docs/benchmark results tests

# --- CLAUDE.md (baseline, PORT=4000, no memory) ---
cp "$SCRIPT_DIR/claude-md/baseline.md" ./CLAUDE.md

# --- Project spec (domain context for the agent) ---
cp "$SCRIPT_DIR/project-spec.md" docs/benchmark/project-spec.md

# --- Extract agent-only sections from change definitions ---
for f in "$SCRIPT_DIR"/changes/[0-9]*.md; do
  sed '/<!-- EVALUATOR NOTES BELOW/,$d' "$f" > docs/benchmark/"$(basename "$f")"
done

# --- Create OpenSpec changes with proposals ---
for f in "$SCRIPT_DIR"/changes/[0-9]*.md; do
  # Derive change name: 01-product-catalog.md -> product-catalog
  change_name=$(basename "$f" .md | sed 's/^[0-9]*-//')

  # Create the change
  openspec new change "$change_name" >/dev/null 2>&1

  # Extract agent input as proposal (everything above EVALUATOR NOTES marker,
  # skipping the first "# Change NN:" header line)
  sed '/<!-- EVALUATOR NOTES BELOW/,$d' "$f" \
    | sed '1{/^# Change/d}' \
    > openspec/changes/"$change_name"/proposal.md

  echo "  ✔ Change: $change_name (proposal ready)"
done

# --- Copy test scripts ---
if [ -d "$SCRIPT_DIR/tests" ]; then
  cp "$SCRIPT_DIR"/tests/test-*.sh tests/
  chmod +x tests/test-*.sh
  # Copy test library (check-conventions.sh etc.)
  if [ -d "$SCRIPT_DIR/tests/lib" ]; then
    mkdir -p tests/lib
    cp "$SCRIPT_DIR"/tests/lib/*.sh tests/lib/
  fi
  echo "  ✔ Test scripts copied to tests/"
fi

# --- Verify extraction ---
count=$(ls docs/benchmark/[0-9]*.md 2>/dev/null | wc -l)
if [ "$count" -ne 12 ]; then
  echo "WARNING: Expected 12 change files, found $count" >&2
fi

if grep -rl "Evaluator Notes" docs/benchmark/*.md 2>/dev/null; then
  echo "ERROR: Evaluator notes leaked into agent-visible files!" >&2
  exit 1
fi

# --- Initial commit ---
git add -A
git commit -m "Initial CraftBazaar setup (baseline run)"

echo ""
echo "=== Done ==="
echo "  Directory: $TARGET"
echo "  CLAUDE.md: baseline (PORT=4000, no memory)"
echo "  Changes:   12 OpenSpec changes with proposals"
echo "  Tests:     12 acceptance test scripts in tests/"
echo ""
echo "Next steps:"
echo "  1. Trust the project (required before set-loop can work):"
echo "     cd $TARGET && claude --dangerously-skip-permissions"
echo "     # Type 'hello', wait for response, Ctrl+C to exit"
echo ""
echo "  2. Start the run:"
echo "     cd $TARGET"
echo "     set-loop start --max 30 --stall-threshold 3 --done manual \"Read CLAUDE.md, then follow the Benchmark Task workflow. There are exactly 12 changes (01-12). Check results/change-*.json to find the next incomplete one. For each: read the change definition in docs/benchmark/, run /opsx:ff to create artifacts, /opsx:apply to implement, run tests/test-NN.sh (it writes results/change-NN.json on pass), commit. Do NOT stop until all 12 results files exist. Do NOT create results files manually.\""
