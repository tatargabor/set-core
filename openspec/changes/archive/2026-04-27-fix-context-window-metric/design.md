# Design: Fix Context Window Metric

## Context

The orchestration framework tracks "how full was the context window" per change so operators can see when an agent is running out of room. This metric drives both a UI badge in the change list and a heuristic warning ("context overflow") in run reports. Two prior fixes already touched this code:

1. The original implementation used `total_input_tokens + total_cache_create` as `context_tokens_end`, which is doubly cumulative.
2. A subsequent partial fix (`lib/set_orch/verifier.py:1761-1793`) replaced that with `max(per-iteration cache_create_tokens)`, with a fallback to `total_cache_create` for older state files.

Both treat `cache_create_tokens` as a context-size proxy, but `cache_creation_input_tokens` from the Anthropic API is a *delta* — the number of tokens written to the prompt cache in that specific API call. In a typical agent loop with hundreds of tool turns, each call appends new tool results to the conversation and creates a new cache version, so the per-call deltas sum to multiples of the actual context size.

Empirical confirmation from `craftbrew-run-20260408-1014`:

| change | stored ctx_end / 1M | sum cache_create / 1M | **real peak per-call (input+cache_read+cache_create)** | real % of 1M |
|---|---:|---:|---:|---:|
| auth-and-accounts | 110% | 305% | **149,490** | **14.9%** |
| product-catalog | 36% | 268% | **169,566** | **17.0%** |

The runs were never close to overflow. The metric reports an alarm that has no relationship to the underlying state.

A second, independent bug compounds this: the frontend (`web/src/components/ChangeTable.tsx:99,106,201`) divides by a hardcoded `200_000`, which was the legacy 200K context window for Claude 3. Claude 4.x defaults to 1M (`lib/set_orch/verifier.py:62-75` already encodes this for the backend), so even a correct backend value would render at 5× inflation in the UI.

Stakeholders:
- Sentinel/operators reviewing run logs.
- Anyone scanning the change list dashboard during a live run.
- Future readers of `openspec/specs/context-window-metrics/spec.md`, which still describes the obsolete formula.

## Goals / Non-Goals

**Goals:**
- The stored `context_tokens_start`/`context_tokens_end` values represent the **peak per-call context size** the model actually saw.
- The frontend computes utilization against the change's actual model window (1M for Claude 4.x by default).
- The spec file matches reality so future contributors don't reintroduce the wrong formula.
- The "context overflow" finding only fires when the new peak metric crosses a meaningful threshold (≥80% of the dynamic window).

**Non-Goals:**
- Per-iteration context sampling charts (a separate UX concern).
- Historical trend visualization across runs.
- Renaming the state field. We reuse `context_tokens_start` / `context_tokens_end` to avoid touching every consumer; the *meaning* changes, not the name.
- Migration of old state files. Pre-fix runs simply have stale (inflated) numbers; we don't rewrite history.
- Context budget enforcement (auto-pause at 80%). That's a future change.

## Decisions

### D1: Compute peak per-call context from raw session JSONL

**Decision:** Add a `peak_per_call_context()` method on `UsageCalculator` (`gui/usage_calculator.py`) that returns `max(input_tokens + cache_read_input_tokens + cache_creation_input_tokens)` across all parsed JSONL lines in the scan window. Surface it through `bin/set-usage --format json` as `peak_per_call_context`. The loop state writer in `lib/loop/state.sh` reads this value during iteration finalize and stores it as `peak_context_tokens` per iteration.

**Alternatives considered:**
- *Use the final API call of each iteration as a proxy* — simpler but incorrect when the iteration's peak occurs mid-loop (e.g., a large tool result that's later evicted).
- *Sample from `set-usage` aggregated counters* — these are sums; they cannot be reverse-engineered into a per-call max.
- *Compute peak inside `state.sh` directly via `jq`* — possible but fragile; the parsing logic already exists in Python in `usage_calculator.py`, and we don't want to duplicate it in shell.

**Why this:** The session JSONL is the authoritative source of per-call data. The Python parser already exists and is the same code path used by the GUI usage display.

### D2: Drop the cumulative-cache_create fallback completely

**Decision:** Remove the `peak = total_cache_create` fallback in `_capture_context_tokens_end` (`verifier.py:1783-1784`). If the new `peak_context_tokens` field is absent from `loop-state.json`, write nothing. The UI already handles "field absent" gracefully.

**Alternatives considered:**
- *Keep the fallback for backwards compat with old loop-state files* — but the fallback is exactly the bug. Showing inflated numbers as a "best effort" is worse than showing nothing, because operators interpret the inflated numbers as real overflow.

**Why this:** "Wrong number" is worse than "no number" for a metric that drives operator decisions. Old runs already shipped; their state files don't need fixing.

### D3: Add `context_window_size` to the orchestration state per change

**Decision:** When the state serializer emits a change object, include `context_window_size` derived from `_context_window_for_model(change.model)`. The frontend reads this field instead of hardcoding 200_000. If the field is absent (old state files), the frontend falls back to 1_000_000 (the current default), not 200_000.

**Alternatives considered:**
- *Port `_context_window_for_model` to TypeScript* — duplicates logic in two languages, easy to drift.
- *Hardcode 1_000_000 in the frontend* — works for 99% of runs but breaks the legacy `[200k]` path.
- *Send the model name to the frontend and let it resolve* — same drift risk as the TS port.

**Why this:** Single source of truth lives in the backend resolver. Frontend stays passive.

### D4: Update the spec file as a MODIFIED delta, not a wholesale rewrite

**Decision:** The change touches the existing `context-window-metrics` capability. Use a delta spec under `specs/context-window-metrics/spec.md` with `## MODIFIED Requirements` for the four affected requirements. Preserve requirement names where possible to keep traceability.

**Why this:** OpenSpec convention. The capability still exists; only the formulas change.

### D5: Rewrite the run-report "OVERFLOW" finding template

**Decision:** Search for the source of the "CONTEXT WINDOW OVERFLOW" finding emitted in run reports. Adjust the threshold check to use the new peak-based metric and the dynamic window. Lower priority than the metric fix itself — if the source isn't found in a quick grep, defer to a follow-up change with a TODO note.

**Why this:** The metric fix alone removes false alarms from the dashboard, but if a templated report still embeds the old language, the false narrative persists in run logs.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `peak_per_call_context` is computed from session JSONL files which may not exist for some loop runs (e.g., resumed sessions, claude --print mode without JSONL writes). | Make the field optional. If missing, leave `context_tokens_start/end` unset and let the UI hide the badge. Document this behavior. |
| Old state files (pre-fix) still have inflated values cached in `orchestration-state.json` for unmerged runs, which will continue to render as overflow until the next status transition. | Acceptable. Operators can manually trigger a re-verify, or the next run will overwrite. We don't migrate. |
| The spec file rename / modification might desync from the run-report template if we don't find it in time. | The proposal explicitly calls out the report-template search as part of the apply phase. If not found, file a follow-up issue rather than blocking the change. |
| Adding a new field `context_window_size` to API responses changes the wire format slightly, which might affect downstream consumers (TUI, MCP tools). | The field is purely additive; older consumers ignore it. We don't remove anything. |
| The new peak computation is slower than reading `total_cache_create` because it parses every JSONL line. | The parser already exists and runs in milliseconds for typical session sizes (< 100MB). Profile only if it shows up in real perf data. |

## Migration Plan

1. **Backend changes** (verifier.py, state.py, loop/state.sh, usage_calculator.py, set-usage). All additive or behind the new `peak_context_tokens` key. Existing fields keep their names.
2. **Frontend changes** (ChangeTable.tsx, api.ts). The new `context_window_size` field is optional in the TS type; falls back to `1_000_000` if missing.
3. **Spec update** (`openspec/specs/context-window-metrics/spec.md` via the delta in this change). Archived during normal `/opsx:archive` flow.
4. **Run-report template rewrite** if found.
5. **Verification:** re-render the dashboard against an existing run that has session JSONLs (e.g., `craftbrew-run-20260408-1014`) and confirm the percentage reads ~15% instead of 141%/241%.

**Rollback:** Pure code change with no data migration. Revert the commit; old behavior returns. State fields keep their names so no schema rollback is needed.

## Open Questions

- **Q1:** Where exactly is the "CONTEXT WINDOW OVERFLOW" finding text generated? It may be in a sentinel script, a run-report markdown template, or post-hoc analysis tooling. Resolve during apply phase via grep across `lib/`, `bin/`, and `templates/`.
- **Q2:** Should `peak_context_tokens` be exposed as its own state field for graphs, separate from `context_tokens_end`? Out of scope for this change — keep the API surface minimal.
- **Q3:** Is there a similar bug in the per-iteration context breakdown (`context_breakdown_start`)? Out of scope unless the same root cause shows up there during apply.
