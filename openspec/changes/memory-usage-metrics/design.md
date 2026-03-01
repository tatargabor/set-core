## Context

Memory hooks inject context into Claude Code sessions across 4 layers (L1-L4), totaling ~3,761 tokens/session on average. We already have injection-side metrics in SQLite (26K+ records across 530 sessions) — but no way to measure whether injected memories actually changed agent behavior. The current "citation rate" (0.59%) uses crude string matching for patterns like "From memory:" which vastly undercounts actual usage.

Key files:
- `bin/wt-hook-memory` — unified hook handler, dispatches by event type
- `lib/metrics.py` — SQLite metrics storage and reporting
- `bin/wt-memory` — CLI with existing `metrics` and `dashboard` subcommands
- `bin/wt-project` — manages CLAUDE.md sections per project (no changes needed for this change)

## Goals / Non-Goals

**Goals:**
- Measure true memory usage rate with context_id inject+cite tracking
- Provide a unified `wt-memory tui` dashboard showing DB stats, hook overhead, and usage signals
- Keep hook latency impact near zero (ID generation is cheap)

**Non-Goals:**
- Real-time polling of active sessions (session-end analysis is sufficient)
- Changing memory recall algorithms or relevance thresholds
- Replacing the existing HTML dashboard (TUI supplements it)

## Decisions

### Decision 1: Context ID format — `[MEM#xxxx]`

**Choice**: 4-char hex ID prefix on each injected memory line: `[MEM#a3f2] memory content...`

**Alternatives considered:**
- UUID: too long, wastes tokens
- Sequential counter: doesn't survive across hook invocations within a turn
- 8-char hash: 4 chars is enough (only needs uniqueness within a session, ~65K namespace)

**Rationale**: 4 hex chars = 16 bits = 65,536 unique IDs per session. Average session has ~50 injections with ~3 results each = ~150 IDs needed. Collision probability negligible. Adds only 10 chars overhead per memory line.

### Decision 2: Passive transcript matching (not active LLM citation)

**Choice**: The Stop hook passively detects memory usage by comparing injected memory content against agent responses in the transcript. No CLAUDE.md rule, no agent burden.

**Alternatives considered:**
- CLAUDE.md rule asking LLM to emit `[MEM_CITE:xxxx]`: adds cognitive load to the agent, unreliable (current explicit citation rate is 0.59%), creates overhead without guaranteed data
- Inline reminder in hook output: still depends on LLM compliance
- rules.yaml topic match: too narrow

**Rationale**: The transcript already contains both the injected memories (in system-reminder blocks) and the agent's responses. A keyword overlap check at session end can detect when injected content influenced a response — without asking the agent to do anything extra. This is heuristic (not 100% precise) but always produces data, unlike active citation which produces nothing when the LLM ignores the rule.

**Algorithm**: For each injected memory, extract 3-5 significant keywords. Scan assistant messages for keyword co-occurrence. If overlap exceeds a threshold (e.g., 2+ keywords from the same memory appear in an assistant message within 5 turns of injection), mark as "passively matched". Also continue detecting legacy explicit patterns ("From memory:", etc.) as bonus signal.

### Decision 3: Store inject+cite pairs in existing SQLite

**Choice**: Add `context_id` column to existing `injections` table + new `mem_cites` table for transcript-scanned cites.

**Alternatives considered:**
- Separate SQLite DB: unnecessarily complex, existing DB works fine
- JSON file: no query capability

**Rationale**: The injections table already has session_id and per-injection records. Adding context_id is a simple ALTER TABLE. The cites table links back to session_id + context_id for join queries.

### Decision 4: TUI as single `wt-memory tui` command

**Choice**: New subcommand that combines three data sources in one view: (1) memory DB stats via `wt-memory stats`, (2) hook metrics from SQLite, (3) usage signals from inject/cite ratio.

**Alternatives considered:**
- Interactive curses TUI: over-engineered for this use case
- Extend existing `wt-memory metrics`: already has output, but cramming more makes it unreadable

**Rationale**: Plain text output (like current `metrics` command) but structured into clear sections. Can be piped, redirected, or read in terminal. No external dependencies needed.

## Risks / Trade-offs

- **[Risk] Passive matching false positives** → Mitigation: require 2+ keyword overlap (not single word), skip common words (the, a, function, file, etc.), and use a conservative threshold. False positives are less harmful than false negatives — overstating usage by 10% is better than showing 0% like the current explicit citation approach.
- **[Risk] Context ID adds token overhead** → Mitigation: 10 chars per memory line × ~3 results per injection = 30 chars = ~8 tokens per injection. Negligible vs. 622 avg tokens per L2 injection.
- **[Risk] ALTER TABLE on live metrics.db** → Mitigation: SQLite handles ALTER TABLE ADD COLUMN safely. Schema migration runs on first access after update.
- **[Risk] TUI data staleness** → Mitigation: TUI reads from SQLite which is flushed at session end. Clearly label "Last updated: <timestamp>" in output.

## Open Questions

- Should we add a `--live` mode to TUI later that reads the session cache JSON for in-progress sessions? (deferred — not in this change)
