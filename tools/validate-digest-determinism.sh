#!/usr/bin/env bash
# validate-digest-determinism.sh
#
# Validates the digest cache by running `set-orch-core digest run` twice on
# each E2E scaffold and asserting byte equality between run-1 (cache miss →
# API call → cache write) and run-2 (cache hit → no API call).
#
# Also captures the planner's strategy log line per scaffold for observation
# (no assertion on which strategy each scaffold lands on — that's logged for
# follow-up threshold tuning if needed).
#
# Usage:
#   ./tools/validate-digest-determinism.sh
#
# Output:
#   Per scaffold: pass/fail, strategy chosen.
#   Aggregate at end.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCAFFOLDS_DIR="$REPO_ROOT/tests/e2e/scaffolds"
SCAFFOLDS=(nano micro-web minishop craftbrew)
TMP_OUT="$(mktemp -d)"

echo "Repo: $REPO_ROOT"
echo "Output dir: $TMP_OUT"
echo "Scaffolds: ${SCAFFOLDS[*]}"
echo

# Clear cache once at the start so run-1 for every scaffold is a true miss.
echo "=== Clearing digest cache (one-time, before all scaffolds) ==="
set-orch-core digest run --spec "$SCAFFOLDS_DIR/${SCAFFOLDS[0]}" --digest-cache-clear --dry-run 2>&1 | tail -1 || true
rm -rf "$HOME/.cache/set-orch/digest-cache"
echo

PASS=0
FAIL=0

for scaffold in "${SCAFFOLDS[@]}"; do
  echo "=== Scaffold: $scaffold ==="
  spec_path="$SCAFFOLDS_DIR/$scaffold"
  if [[ ! -d "$spec_path" ]]; then
    echo "  SKIP: scaffold dir not found at $spec_path"
    continue
  fi

  run1_dir="$TMP_OUT/${scaffold}.run1"
  run2_dir="$TMP_OUT/${scaffold}.run2"
  mkdir -p "$run1_dir" "$run2_dir"

  # Run 1: cache miss → API call → write
  echo "  run 1 (cache miss expected, API call)..."
  set-orch-core digest run --spec "$spec_path" --dir "$run1_dir" 2> "$run1_dir/stderr.log" || {
    echo "  FAIL: run-1 errored. See $run1_dir/stderr.log"
    FAIL=$((FAIL + 1))
    continue
  }

  # Run 2: cache hit → byte-identical raw
  echo "  run 2 (cache hit expected, no API call)..."
  set-orch-core digest run --spec "$spec_path" --dir "$run2_dir" 2> "$run2_dir/stderr.log" || {
    echo "  FAIL: run-2 errored. See $run2_dir/stderr.log"
    FAIL=$((FAIL + 1))
    continue
  }

  # Compare requirements.json (the deterministic digest output)
  if diff -q "$run1_dir/requirements.json" "$run2_dir/requirements.json" > /dev/null 2>&1; then
    echo "  PASS: requirements.json byte-identical between runs"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: requirements.json differs between runs"
    diff -u "$run1_dir/requirements.json" "$run2_dir/requirements.json" | head -20
    FAIL=$((FAIL + 1))
    continue
  fi

  # Sanity: run-2 stderr should contain "digest cache hit"
  if grep -q "digest cache hit" "$run2_dir/stderr.log"; then
    echo "  GOOD: run-2 logged 'digest cache hit'"
  else
    echo "  WARN: run-2 stderr does not contain 'digest cache hit' (cache may not have intercepted)"
  fi

  # Strategy log (observed, not asserted)
  strategy_line="$(grep -h "decompose strategy=" "$run1_dir/stderr.log" "$run2_dir/stderr.log" 2>/dev/null | tail -1 || true)"
  if [[ -n "$strategy_line" ]]; then
    echo "  strategy: $strategy_line"
  fi
  echo
done

echo "=== Summary ==="
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  Output preserved at: $TMP_OUT"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
