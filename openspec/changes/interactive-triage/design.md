# Design: interactive-triage

## Context

The triage pipeline exists and works: digest finds ambiguities, generates triage.md, the triage gate checks decisions, and the planner resolves deferred items. What's missing is a practical way for humans to interact with it. The current options are edit a markdown file by hand (CLI mode) or let everything auto-defer (automated mode). This change adds two interaction surfaces — web form and prompt — both writing to the same underlying triage.md + ambiguities.json storage.

Existing code:
- `lib/set_orch/digest.py` — `generate_triage_md()`, `parse_triage_md()`, `merge_triage_to_ambiguities()`
- `lib/set_orch/planner.py` — `check_triage_gate()`, `_parse_triage_decisions()`
- `lib/set_orch/api/orchestration.py` — `GET /api/{project}/digest` (reads triage.md as raw text)
- `web/src/components/DigestView.tsx` — renders triage tab as `<MarkdownPanel>`

## Goals / Non-Goals

**Goals:**
- Human-in-the-loop triage via web dashboard and prompt
- Immutable per-item decisions (submit once, no undo)
- Sentinel wait mode for interactive orchestration sessions
- Both surfaces share the same storage (triage.md + ambiguities.json)

**Non-Goals:**
- Type-specific UI per ambiguity type (universal fix/defer/ignore for all types)
- Real-time push notifications to sentinel (polling via loop iteration)
- Batch submit or drag-and-drop reordering

## Decisions

### D1: Per-item POST, not batch submit
Each ambiguity decision is submitted individually via `POST /api/{project}/triage/{amb_id}`. The decision is written to triage.md and merged to ambiguities.json immediately.

**Why:** Enables incremental triage — user can resolve a few items from web, then switch to prompt for the rest. No "form state" to manage, no partial-submit edge cases.

**Alternative considered:** Batch POST with all decisions at once. Rejected because it requires the user to complete all items before any take effect, and doesn't support mixed web+prompt workflows.

### D2: Immutable decisions — 409 on re-submit
Once a decision is written, it cannot be changed. Re-submitting returns 409 Conflict.

**Why:** Simplifies the state machine. The planner may already be using deferred items in its prompt. Allowing edits after planning starts would create inconsistency. If a decision was truly wrong, the user can re-run digest (which regenerates triage.md with a fresh start).

**Alternative considered:** Allow edits before planning starts, lock after. Rejected because tracking "has planning started" per-item adds complexity with minimal benefit.

### D3: Sentinel uses next-loop polling, not webhooks
The sentinel doesn't get notified when triage completes. It simply re-checks `check_triage_gate()` on each loop iteration. If untriaged items remain, it logs and skips to next iteration.

**Why:** Zero new infrastructure. The sentinel loop already runs periodically. Adding webhook or SSE would require a subscription mechanism between web server and sentinel process.

**Alternative considered:** WebSocket from web UI to sentinel. Over-engineered for a gate that blocks once per orchestration run.

### D4: triage_mode in orchestration config
A new `triage_mode` field in orchestration.yaml controls behavior:
- `auto` (default) — auto-defer all, existing behavior preserved
- `interactive` — sentinel waits for human decisions

**Why:** E2E runs must auto-defer (no human available). Production orchestration should wait. The config is per-project, set once.

### D5: Write to triage.md as canonical storage, derive JSON from it
The POST endpoint writes to triage.md (updating the `**Decision:**` and `**Note:**` fields), then calls `merge_triage_to_ambiguities()` to sync to ambiguities.json. The GET endpoint reads ambiguities.json + triage.md to build the response.

**Why:** triage.md is the existing human-readable format. All existing code (planner, gate check) reads from it. Writing to triage.md and deriving JSON keeps one source of truth.

**Alternative considered:** Write to ambiguities.json directly, generate triage.md from it. Would require rewriting `_parse_triage_decisions()` and `check_triage_gate()` to read JSON instead.

### D6: Universal fix/defer/ignore for all ambiguity types
All types (underspecified, contradictory, implicit_assumption, missing_reference) get the same three buttons. The note textarea carries type-specific context.

**Why:** For contradictory items, the user writes "design-system.md wins" in the note + clicks ignore. For implicit_assumption, they write "confirmed" in the note + click defer. The planner gets the note and understands. No custom UI per type means less code and no ambiguity about which buttons apply when.

## Risks / Trade-offs

- [Risk] User submits "fix" but doesn't actually fix the spec → pipeline stuck at `has_fixes` forever → **Mitigation:** Clear messaging in web UI: "This item blocks planning until the spec is corrected and digest re-run"
- [Risk] Sentinel loop interval too slow for responsive triage UX → **Mitigation:** Sentinel loop is typically 30-60s; triage is a one-time gate per orchestration run, not time-critical
- [Risk] triage.md format is fragile (regex parsing) → **Mitigation:** Existing parsers work; new write logic uses the same format. Add integration test for round-trip write→parse.

## Open Questions

_(none — all decisions made during explore phase)_
