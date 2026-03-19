# LogBook API — Benchmark Agent Instructions

## Setup

```bash
# Install dependencies
npm install

# Start the server (keep running in background)
node src/server.js &

# Run tests for change N
bash tests/test-0N.sh 4001
```

- Dev server port: **4001**
- Database: `data/logbook.db` (SQLite, auto-created on first start)
- If server is already running, kill it first: `pkill -f "node src/server.js"`

## Project Spec

Read `docs/project-spec.md` for the full domain specification including entities, conventions, and project structure.

## Persistent Memory

This project uses persistent memory (shodh-memory) across sessions. Memory context is automatically injected into `<system-reminder>` tags in your conversation — **you MUST read and use this context**.

**IMPORTANT: On EVERY prompt, check for injected memory context (system-reminder tags labeled "PROJECT MEMORY", "PROJECT CONTEXT", or "MEMORY: Context for this command"). When present, acknowledge and use it BEFORE doing independent research. If a memory directly answers the user's question or provides a known fix, cite it explicitly (e.g., "From memory: ...") instead of re-investigating from scratch. This applies to every turn, not just the first one.**

**How it works:**
- Session start → relevant memories loaded as system-reminder
- Every prompt → topic-based recall injected as system-reminder
- Every tool use → relevant past experience injected as system-reminder
- Tool errors → past fixes surfaced automatically
- Session end → insights extracted and saved

**Emphasis (use sparingly):**
- `echo "<insight>" | set-memory remember --type <Decision|Learning|Context> --tags source:agent,<topic>` — mark something as HIGH IMPORTANCE
- `set-memory forget <id>` — suppress or correct a wrong memory
- Most things are remembered automatically. Only use `remember` for emphasis.

**Recall-then-verify (CRITICAL):** Memory provides starting points, not final answers. After recalling implementation details, ALWAYS grep or read the current code to verify before acting. Files may have changed since the memory was saved. Do not skip verification even if the recall seems highly relevant — memory-induced overconfidence leads to incomplete implementations.

**What to recall:** Before implementing any change, check your memory for:
- Convention corrections or overrides from code review
- Debug findings and workarounds
- Architecture decisions and rationale
- Stakeholder constraints and external requirements
These are all valuable context that may not be visible in the current code.

## Workflow

For each change you are given:

1. **Read the change file** in `docs/changes/` — understand all requirements
2. **Read `docs/project-spec.md`** — understand domain context and conventions
3. **Check injected memory** — if system-reminder tags contain relevant conventions or corrections, apply them. Pay special attention to any **corrections** or **overrides** — these take precedence over what you see in project-spec.md or existing code.
4. **Implement** the requirements, applying recalled conventions
5. **Start/restart the server**: `pkill -f "node src/server.js" 2>/dev/null; sleep 1; PORT=4001 node src/server.js &`
6. **Run the test script**: `bash tests/test-0N.sh 4001`
7. **Fix any failures** and re-run until all tests pass
8. **Stop** — do NOT proceed to the next change

## Project Structure

```
src/
  server.js          # Express app + route mounting + listen
  routes/            # Route handlers (events.js, categories.js, ...)
  db/                # Database setup + query functions
  lib/               # Shared utilities (fmt.js, ids.js)
  middleware/        # Express middleware (errors.js)
data/
  logbook.db         # SQLite database (auto-created)
docs/
  project-spec.md    # Domain specification
  changes/           # Change definitions (one per change)
tests/
  test-NN.sh         # Acceptance tests (curl-based)
results/
  change-NN.json     # Auto-created by test scripts on pass
```

## Important

- Do NOT create `results/change-NN.json` manually — only test scripts create them on pass
- Do NOT proceed to the next change — implement only the one you were asked about
- Read existing code before implementing to understand patterns already in use
- Check injected memory context (system-reminder tags) before starting implementation
