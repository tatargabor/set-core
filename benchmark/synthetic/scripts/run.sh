#!/bin/bash
# run.sh — Run MemoryProbe benchmark sessions
# Usage: ./run.sh <project-dir> [--start N] [--end N]

set -euo pipefail

PROJECT="${1:?Usage: ./run.sh <project-dir> [--start N] [--end N]}"
shift

START=1
END=5

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) START="$2"; shift 2 ;;
    --end) END="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

cd "$PROJECT"

# Detect port from CLAUDE.md
PORT=4000
if grep -q "4001" CLAUDE.md 2>/dev/null; then
  PORT=4001
fi

echo "=== MemoryProbe v2 Runner ==="
echo "  Project: $PROJECT"
echo "  Port:    $PORT"
echo "  Changes: $START → $END"
echo ""

TOTAL_START=$(date +%s)

for N in $(seq "$START" "$END"); do
  NN=$(printf "%02d" "$N")
  CHANGE_FILE="docs/changes/$(ls docs/changes/ | grep "^${NN}-" | head -1)"

  if [[ ! -f "$CHANGE_FILE" ]]; then
    echo "WARNING: No change file for C$NN — skipping"
    continue
  fi

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Session $NN: $CHANGE_FILE"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  SESSION_START=$(date +%s)

  # Kill any running server on our port
  pkill -f "node src/server.js" 2>/dev/null || true
  fuser -k "$PORT"/tcp 2>/dev/null || true
  sleep 1

  # Run Claude session (env -u CLAUDECODE allows running from within another claude session)
  echo "  Starting claude session..."

  # Mode B prompt includes explicit save instruction; Mode A is implementation-only
  if grep -q "set-memory" CLAUDE.md 2>/dev/null; then
    PROMPT="Follow the workflow in CLAUDE.md. Implement the change described in $CHANGE_FILE. Read the change file and docs/project-spec.md first. Check injected memory context in system-reminder tags for relevant conventions and corrections. Implement the requirements. Start the server with: PORT=$PORT node src/server.js & — then run: bash tests/test-${NN}.sh $PORT — fix any failures until all tests pass. Do not proceed to the next change."
  else
    PROMPT="Implement the change described in $CHANGE_FILE. Read it first, then read docs/project-spec.md for conventions. Implement the requirements. Start the server with: PORT=$PORT node src/server.js & — then run: bash tests/test-${NN}.sh $PORT — fix any failures until all tests pass. Do not proceed to the next change."
  fi

  # Mode B (with hooks) needs more turns due to hook overhead injecting context
  if grep -q "set-memory" CLAUDE.md 2>/dev/null; then
    MAX_TURNS=50
  else
    MAX_TURNS=30
  fi

  env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude --dangerously-skip-permissions \
    -p "$PROMPT" \
    --max-turns "$MAX_TURNS" \
    --verbose \
    --output-format stream-json \
    > "results/session-${NN}.jsonl" 2>"results/session-${NN}.err" || true

  # Extract the final result line (type=result) for token/cost summary
  grep '"type":"result"' "results/session-${NN}.jsonl" | tail -1 > "results/session-${NN}.json" 2>/dev/null || true
  echo "  Claude session finished ($(wc -l < "results/session-${NN}.jsonl") lines output)"

  SESSION_END=$(date +%s)
  SESSION_TIME=$(( SESSION_END - SESSION_START ))

  # Kill server after session
  pkill -f "node src/server.js" 2>/dev/null || true
  sleep 1

  # --- Post-session memory extraction (Mode B only) ---
  # Agents consistently run out of turns before saving to memory.
  # This step extracts Developer Notes corrections and code conventions
  # from the change file and saves them — simulating what a well-functioning
  # save hook would do. Only runs in memory mode (CLAUDE.md mentions set-memory).
  if grep -q "set-memory" CLAUDE.md 2>/dev/null && command -v set-memory &>/dev/null; then
    echo "  Extracting conventions to memory..."
    bash "$(dirname "$0")/post-session-save.sh" "$CHANGE_FILE" "$NN" 2>/dev/null || true
  fi

  # Commit changes
  git add -A
  git commit -m "Change $NN complete (${SESSION_TIME}s)" --allow-empty > /dev/null 2>&1 || true

  # Run test independently to get results
  PORT=$PORT node src/server.js &
  SERVER_PID=$!
  sleep 2

  if bash "tests/test-${NN}.sh" "$PORT"; then
    echo "  >> Test $NN: ALL PASSED"
  else
    echo "  >> Test $NN: SOME FAILURES"
  fi

  kill $SERVER_PID 2>/dev/null || true
  wait $SERVER_PID 2>/dev/null || true

  echo "  >> Session time: ${SESSION_TIME}s"
  echo ""

  # Brief pause for memory flush
  sleep 5
done

TOTAL_END=$(date +%s)
TOTAL_TIME=$(( TOTAL_END - TOTAL_START ))

echo "=== MemoryProbe Complete ==="
echo "  Total time: ${TOTAL_TIME}s ($(( TOTAL_TIME / 60 ))m)"
echo "  Results: $(ls results/change-*.json 2>/dev/null | wc -l)/$(( END - START + 1 )) changes passed"
echo ""
echo "Run scoring:"
echo "  bash scripts/score.sh ."
