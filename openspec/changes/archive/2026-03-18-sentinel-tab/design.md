# Design: sentinel-tab

## Context

The sentinel supervisor monitors orchestration runs from a separate terminal. Today it outputs to stdout (agent mode) or silently restarts processes (bash mode). Neither mode produces structured output that other tools can consume. The wt-web dashboard has 10 tabs but no sentinel visibility.

The messaging system (wt-control-chat) exists but the sentinel doesn't poll for incoming messages — it only sends outbound messages to the user via terminal output.

### Current architecture
```
Bash sentinel (bin/wt-sentinel)     Agent sentinel (/wt:sentinel skill)
├── 10s poll via kill -0             ├── 30s poll via background bash
├── mtime-based liveness            ├── State.json-based decisions
├── 2 event types to JSONL          ├── Unstructured terminal output
└── No inbox                        └── No inbox
```

## Goals / Non-Goals

**Goals:**
- Structured event stream from both sentinel modes
- Findings tracking (bugs, observations, assessments) as structured JSON
- 3-5s bidirectional messaging between user (wt-web) and sentinel
- wt-web Sentinel tab for monitoring and communication
- `.wt/` directory as the runtime home for sentinel data

**Non-Goals:**
- Replacing the terminal-based sentinel workflow (sentinel still starts in terminal)
- WebSocket streaming for sentinel events (1s REST polling is sufficient for this data rate)
- Starting/stopping sentinel from wt-web
- Migrating non-sentinel runtime files to `.wt/` (separate change)

## Decisions

### 1. Python library with CLI wrappers

**Decision:** New `lib/wt_orch/sentinel/` package with CLI entry points.

**Why not just prompt changes?** The agent sentinel skill could theoretically be updated to write JSON files directly via bash commands. But: (a) the bash sentinel also needs the same capability, (b) structured JSON manipulation in bash is fragile, (c) Python gives us proper file locking, atomic writes, and testability.

**Why not just Python (no CLI)?** The bash sentinel (`bin/wt-sentinel`) is 560 lines of battle-tested bash. Rewriting it in Python is out of scope. CLI wrappers let bash call Python for structured operations while keeping its process supervision logic.

**Alternative considered:** Node.js — rejected because the rest of the backend is Python (FastAPI).

### 2. File-based communication (not WebSocket)

**Decision:** Sentinel writes files → wt-web reads files via REST endpoints with 1s polling.

**Why not WebSocket?** The sentinel runs in a separate process/terminal — there's no persistent connection to wt-web. File-based communication is the natural bridge. The event rate is low (~4 events/minute during normal operation, burst of ~10 during incidents). 1s REST polling handles this easily.

**Why not inotify/watchdog?** Added complexity for marginal latency improvement. The wt-web backend already polls orchestration-state.json; adding sentinel file polling is consistent.

### 3. Split sleep for inbox responsiveness

**Decision:** Instead of one long sleep, split into N shorter sleeps with inbox checks between them.

```
Bash (10s poll):  sleep 5 → inbox → sleep 5 → state poll
Agent (30s poll): sleep 3 → inbox → sleep 3 → ... (10x) → state poll
```

**Why not inotifywait?** It works but adds a dependency and complexity. The inbox check is a single file read (<1ms). Polling at 3-5s intervals is cheap and reliable.

**Why not reduce the main poll interval?** State polling is expensive (reads state.json, may trigger LLM in agent mode). Inbox check is a no-op file read — different cost profiles.

### 4. events.jsonl + findings.json (separate files)

**Decision:** Events are append-only JSONL (stream). Findings are a structured JSON document (state).

**Why two formats?** Events are a log — append-only, ordered, potentially large. Findings are a small stateful document that gets updated in place (finding status changes). Different access patterns → different formats.

### 5. `.wt/sentinel/` directory

**Decision:** All sentinel runtime data lives under `.wt/sentinel/` in the project root, gitignored via `/.wt/`.

**Why `.wt/` and not `.claude/sentinel/`?** `.claude/` is for configuration (settings, commands, skills, rules). Runtime data mixed with config causes the gitignore fragmentation problem we already encountered. `.wt/` is the new convention for runtime-only data.

**Why project-local and not `~/.cache/`?** Multiple projects run simultaneously. Project-local means wt-web can find sentinel data at a known relative path without configuration.

### 6. Sentinel identity via status.json

**Decision:** The sentinel writes `status.json` on startup with its identity. "Az lesz a sentinel aki utoljára aktiválja a skill-t."

**Why?** wt-web needs to know: (a) is a sentinel running? (b) who is it? (c) how to send messages to it. `status.json` answers all three. The `member` field is the messaging address.

## Module structure

```
lib/wt_orch/sentinel/
├── __init__.py           # Package init, convenience imports
├── events.py             # SentinelEventLogger class
├── findings.py           # SentinelFindings class
├── inbox.py              # check_inbox(), ack_inbox() functions
├── status.py             # SentinelStatus class (register, heartbeat, deactivate)
└── rotation.py           # rotate() — archive events + findings for new run

bin/
├── wt-sentinel           # (existing) bash sentinel — modified to call CLI tools
├── wt-sentinel-log       # CLI: event logging
├── wt-sentinel-finding   # CLI: findings CRUD
├── wt-sentinel-inbox     # CLI: inbox check
├── wt-sentinel-status    # CLI: status management
└── wt-sentinel-rotate    # CLI: run rotation

web/src/components/
└── SentinelPanel.tsx      # Sentinel tab component

web/src/hooks/
└── useSentinelData.ts     # Polling hook for sentinel REST endpoints

lib/wt_orch/
└── api.py                 # (existing) — add sentinel REST endpoints
```

## Data flow

```
┌─ Sentinel (terminal) ───────────────────────────────┐
│                                                      │
│  State poll (15-30s)  ──► wt-sentinel-log poll ...   │
│  Crash detected       ──► wt-sentinel-log crash ...  │
│  Finding discovered   ──► wt-sentinel-finding add .. │
│  Inbox check (3-5s)   ──► wt-sentinel-inbox check    │
│                            │                         │
│  All CLI tools call ───────┘                         │
│  Python library which                                │
│  writes to .wt/sentinel/                             │
└──────────────────────────────────────────────────────┘
              │ filesystem writes
              ▼
┌─ .wt/sentinel/ ─────────────────────────────────────┐
│  events.jsonl  │  findings.json  │  status.json      │
└──────────────────────────────────────────────────────┘
              │ filesystem reads
              ▼
┌─ wt-web backend (FastAPI) ──────────────────────────┐
│  GET /sentinel/events?since=...                      │
│  GET /sentinel/findings                              │
│  GET /sentinel/status                                │
│  POST /sentinel/message → outbox file write          │
└──────────────────────────────────────────────────────┘
              │ REST (1s poll)
              ▼
┌─ wt-web frontend (React) ──────────────────────────┐
│  SentinelPanel.tsx                                   │
│  ├── StatusBar (active/inactive, member, uptime)     │
│  ├── EventStream (scrolling log, color-coded)        │
│  ├── FindingsPanel (severity badges, status)         │
│  ├── AssessmentSection (phase summaries)             │
│  └── MessageInput (text → POST /sentinel/message)    │
└──────────────────────────────────────────────────────┘
```

## Risks / Trade-offs

- **[Risk] File locking on concurrent writes** → Mitigation: only one sentinel writes at a time (enforced by existing flock in bash sentinel). The wt-web backend only reads.
- **[Risk] events.jsonl grows indefinitely** → Mitigation: rotation on new run. For very long runs, the wt-web `since` filter avoids loading the entire file.
- **[Risk] Inbox check overhead in tight loop** → Mitigation: it's a single file stat + read, <1ms. Even at 3s intervals this is negligible.
- **[Risk] Backward compatibility** → Mitigation: all changes are additive. Existing sentinel behavior is preserved. If CLI tools aren't available (old wt-tools version), sentinel falls back to current behavior.

## Open Questions

- Should the wt-web Sentinel tab be visible even when no sentinel has ever run (empty state), or only appear when status.json exists?
