# Execution Model

## Overview

MemoryProbe runs 5 (or 3) changes as separate Claude sessions. A runner script orchestrates the sessions, collects results, and runs scoring.

## Directory Structure

```
benchmark/synthetic/
├── README.md                    # Quick-start guide
├── run-guide.md                 # Detailed execution protocol
├── project-spec.md              # LogBook domain spec (~40 lines)
├── scoring-rubric.md            # Trap definitions + expected results
│
├── changes/
│   ├── 01-event-crud.md         # SEED: establish conventions
│   ├── 02-tags-filtering.md     # GAP: unrelated work
│   ├── 03-comments-activity.md  # PROBE: test conventions
│   ├── 04-dashboard-export.md   # PROBE: test conventions
│   └── 05-bulk-operations.md    # PROBE: test conventions
│
├── tests/
│   ├── test-01.sh               # CRUD + convention checks
│   ├── test-02.sh               # Tags + filtering checks
│   ├── test-03.sh               # Comments + convention probes
│   ├── test-04.sh               # Dashboard + convention probes
│   └── test-05.sh               # Bulk ops + convention probes
│
├── claude-md/
│   ├── baseline.md              # CLAUDE.md for Mode A (no memory)
│   └── with-memory.md           # CLAUDE.md for Mode B (with memory)
│
├── scripts/
│   ├── init.sh                  # Bootstrap project (--with-memory flag)
│   ├── run.sh                   # Run all sessions sequentially
│   ├── pre-seed.sh              # Inject memories for Mode C
│   └── score.sh                 # Automated scoring
│
└── results/                     # Created during runs
    ├── mode-a/
    │   ├── change-01.json
    │   ├── ...
    │   └── score.json
    ├── mode-b/
    │   └── ...
    └── mode-c/
        └── ...
```

## Bootstrap (init.sh)

Single script with mode flag:

```bash
./init.sh --mode a --target ~/bench/probe-a    # Baseline
./init.sh --mode b --target ~/bench/probe-b    # With memory
./init.sh --mode c --target ~/bench/probe-c    # Pre-seeded
```

Steps:
1. Validate prerequisites: `node`, `npm`, `claude` CLI, `set-memory` (modes B/C only)
2. Create target directory, `git init`
3. `npm init -y && npm install express better-sqlite3 nanoid`
4. Copy `project-spec.md` to `docs/`
5. Copy change files to `docs/changes/` (strip evaluator notes with sed)
6. Copy test scripts to `tests/`
7. Deploy CLAUDE.md (baseline or with-memory based on mode)
8. For mode B: `wt-deploy-hooks --memory .` (enable memory hooks)
9. For mode C: run `pre-seed.sh` (inject convention memories)
10. Initial commit
11. Print next steps

## Session Runner (run.sh)

Runs each change as a separate Claude invocation:

```bash
./run.sh <project-dir> [--start N] [--end N]
```

Per session:
```bash
claude --dangerously-skip-permissions \
  -p "Implement the change described in docs/changes/0${N}.md. Read it first, then implement. Run tests/test-0${N}.sh when done. Do not proceed to the next change." \
  --max-turns 25 \
  --output-format json \
  > "results/session-0${N}.json" 2>&1
```

Key flags:
- `--dangerously-skip-permissions`: No human interaction needed
- `--max-turns 25`: Per-session iteration limit (prevents runaway)
- `--output-format json`: Machine-parseable output for diagnostics

Between sessions:
- Commit all changes: `git add -A && git commit -m "Change 0N complete"`
- Run test: `bash tests/test-0N.sh`
- Record test result: `results/change-0N.json`
- Small delay (5s) for memory system to flush

## Pre-Seed Script (pre-seed.sh)

For Mode C only. Injects 6 perfectly-written convention memories:

```bash
#!/bin/bash
# pre-seed.sh — Inject convention memories for Mode C

echo 'LogBook project convention: All list endpoints return {entries: [...], paging: {current: N, size: N, count: N, pages: N}}. Query params: ?page=1&size=20. Key names: entries (not data), paging (not pagination), current (not page), size (not limit), count (not total), pages (not totalPages).' \
  | set-memory remember --type Decision --tags "convention,pagination,api-format"

echo 'LogBook project convention: All error responses use {fault: {reason: string, code: string, ts: string}}. Key: fault (not error), reason (not message). Error codes are SCREAMING_SNAKE. ts is ISO timestamp. Example: {fault: {reason: "Event not found", code: "EVT_NOT_FOUND", ts: "2026-02-17T10:30:00Z"}}' \
  | set-memory remember --type Decision --tags "convention,error-format,api-format"

echo 'LogBook project convention: Soft-delete uses removedAt column (DATETIME, nullable). NOT deletedAt, NOT isDeleted. All queries filter WHERE removedAt IS NULL. Archive = set removedAt to now. Purge = hard DELETE where removedAt older than threshold.' \
  | set-memory remember --type Decision --tags "convention,soft-delete,database"

echo 'LogBook project convention: All human-readable timestamps use fmtDate(date) from lib/fmt.js. Returns YYYY/MM/DD HH:mm (slash-separated, 24h, no seconds). Import: const {fmtDate} = require("./lib/fmt") or similar. Do NOT use toISOString(), toLocaleDateString(), dayjs, moment, or inline formatting.' \
  | set-memory remember --type Decision --tags "convention,date-format,utility"

echo 'LogBook project convention: All entity IDs use prefixed nanoid format. Events: evt_<nanoid(12)>, Categories: cat_<nanoid(12)>, Comments: cmt_<nanoid(12)>, Tags: tag_<nanoid(12)>, Batches: bat_<nanoid(12)>. Use nanoid package. Generate at insert time. Do NOT use auto-increment, UUID, CUID, or ULID.' \
  | set-memory remember --type Decision --tags "convention,id-format,database"

echo 'LogBook project convention: ALL successful API responses include ok: true at the top level. Format: {ok: true, ...payload}. For lists: {ok: true, entries: [...], paging: {...}}. For single items: {ok: true, event: {...}}. For actions: {ok: true, archived: 5}. The ok field is always present and always true for 2xx responses.' \
  | set-memory remember --type Decision --tags "convention,response-format,api-format"

echo "Pre-seeded 6 convention memories."
```

## CLAUDE.md Variants

### baseline.md (Mode A)

```markdown
# LogBook API

## Setup
- Dev server: `node src/server.js` (port 3000)
- Tests: `bash tests/test-NN.sh 3000`

## Project Spec
Read `docs/project-spec.md` for domain context.

## Workflow
1. Read the change file in `docs/changes/`
2. Implement the requirements
3. Run the test script
4. Fix any failures
5. Do NOT proceed to the next change — stop after this one

## Structure
src/
  server.js          # Express app + routes
  routes/            # Route handlers
  db/                # Database access layer
  lib/               # Shared utilities
  middleware/        # Express middleware
tests/
  test-NN.sh        # Acceptance tests (curl-based)
```

### with-memory.md (Mode B)

Same as baseline, plus:

```markdown
## Memory

Before implementing, recall relevant project context:
\`\`\`bash
set-memory recall "LogBook conventions" --limit 5 --mode hybrid
set-memory recall "project patterns API format" --limit 5 --mode semantic
\`\`\`

When you discover project conventions or patterns, save them:
\`\`\`bash
echo "<convention description>" | set-memory remember --type Decision --tags "convention,<topic>"
\`\`\`

After completing the change, save what you learned:
\`\`\`bash
echo "<insight>" | set-memory remember --type Learning --tags "change:0N,<topic>"
\`\`\`
```

## Test Scripts

Each test script follows this pattern:

```bash
#!/bin/bash
PORT="${1:-3000}"
BASE="http://localhost:$PORT"
PASS=0; FAIL=0

check() {
  local desc="$1"; shift
  if eval "$@" > /dev/null 2>&1; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc"
    FAIL=$((FAIL + 1))
  fi
}

# Functional checks
check "GET /events returns 200" \
  '[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE/events")" = "200" ]'

# Convention checks (in probe changes)
check "T1: pagination uses paging.current" \
  'curl -s "$BASE/events" | python3 -c "import json,sys; d=json.load(sys.stdin); assert \"paging\" in d and \"current\" in d[\"paging\"]"'

# Results
echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ $FAIL -eq 0 ]; then
  mkdir -p results
  echo "{\"change\": \"0N\", \"pass\": $PASS, \"fail\": 0}" > results/change-0N.json
fi

exit $((FAIL > 0 ? 1 : 0))
```

**Important**: Test scripts for C03-C05 include BOTH functional checks AND convention checks. Convention checks verify the grep patterns at runtime by inspecting actual API responses, not just source code.

## Timing Estimates

| Mode | Changes | Sessions | Est. Time |
|------|---------|----------|-----------|
| A (baseline) | C01-C05 | 5 | 25-35 min |
| B (full memory) | C01-C05 | 5 | 25-35 min |
| C (pre-seeded) | C03-C05 | 3 | 15-20 min |
| **Full comparison (A+B)** | | **10** | **50-70 min** |
| **Full comparison (A+B+C)** | | **13** | **65-90 min** |

vs CraftBazaar: 24 sessions × 10-15 min = 4-5 hours

## Failure Handling

- If a session exceeds 25 turns: force-stop, record as TIMEOUT
- If a test fails after session: record partial results, continue to next change
- If memory system is down: Mode A unaffected, Mode B degrades to Mode A behavior, Mode C cannot start
- If server crashes: restart before next session
