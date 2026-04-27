# Proposal: Fix Context Window Metric (peak vs cumulative cache writes)

## Why

The orchestration dashboard reports misleading "context window overflow" warnings — runs show 141%, 241%, even 304% utilization, suggesting catastrophic context overflow. In reality, those runs peaked at 14.9–17% of the 1M context window. The bug has been root-caused twice in past sessions but only partially fixed: the backend formula in `verifier.py` now uses `max(per-iter cache_create_tokens)` instead of the cumulative `total_cache_create`, but per-iter `cache_create_tokens` is *itself* cumulative across all API calls within a single iteration. With 800+ tool turns per iteration, the per-iter sum reaches multi-million tokens while the actual peak context per single API call stays around 150K. The frontend additionally divides by a hardcoded 200K window even though Claude 4.x runs with a 1M default. The result is a metric that looks like an overflow alarm but encodes neither peak nor utilization correctly.

This is harmful because it misdirects post-run diagnosis: the most recent run produced a "CONTEXT WINDOW OVERFLOW" finding pointing at agents that never came close to the limit, while real failure causes go uninvestigated. Operators learn to ignore the metric, which then masks a real overflow when one eventually occurs.

## What Changes

- **BREAKING (metric semantics):** Replace `context_tokens_start` / `context_tokens_end` semantics in orchestration state. The new value is the **peak per-call context size** observed during the loop, computed as `max(input_tokens + cache_read_input_tokens + cache_creation_input_tokens)` across all Claude API calls in all iterations of the loop. The old field names are reused to avoid a state migration, but consumers must understand the new meaning.
- **New helper:** Extend `set-usage` (or add a sibling helper in `gui/usage_calculator.py`) to emit a `peak_per_call_context` field per session JSONL scan. The loop state writer in `lib/loop/state.sh` calls this and stores it under `peak_context_tokens` per iteration.
- **Verifier rewrite:** `_capture_context_tokens_start` and `_capture_context_tokens_end` in `lib/set_orch/verifier.py` switch from `cache_create_tokens` (cumulative delta) to `peak_context_tokens` (per-call peak). The fallback path that still reads `total_cache_create` is removed — there is no meaningful fallback for old loop-state files; absent peak data leaves the field unset.
- **Window size dynamic per model:** The frontend ChangeTable component (`web/src/components/ChangeTable.tsx`) stops dividing by hardcoded 200,000. Instead, the orchestration state serializer adds a `context_window_size` field per change (derived from the model name via the existing `_context_window_for_model` helper in `verifier.py`), and the frontend divides by that.
- **Spec realignment:** `openspec/specs/context-window-metrics/spec.md` is updated (modified delta) to describe the new formula and dynamic window size. The old "stored in 200K window" requirement is rewritten.
- **Run report cleanup:** The post-run summary template (wherever the "CONTEXT WINDOW OVERFLOW" block came from) is checked and reworded so the metric is only flagged when the new peak-based calculation actually exceeds 80% of the dynamic window.

## Capabilities

### Modified Capabilities

- `context-window-metrics` — Reformulates how context utilization is measured and displayed. The capability still exists; only its requirements change. Delta spec under `specs/context-window-metrics/spec.md`.

### New Capabilities

None.

## Impact

- **Affected code (Layer 1, core):**
  - `lib/set_orch/verifier.py` — `_capture_context_tokens_start`, `_capture_context_tokens_end`, `_context_window_for_model`
  - `lib/set_orch/state.py` (or wherever orchestration state is serialized to API JSON) — add `context_window_size` field
  - `lib/loop/state.sh` — store `peak_context_tokens` per iteration
- **Affected code (helpers):**
  - `gui/usage_calculator.py` — add a `peak_per_call_context()` method that returns `max(inp + cache_read + cache_create)` across calls
  - `bin/set-usage` — surface the new field in `--format json` output
- **Affected code (Layer 2, web):**
  - `web/src/components/ChangeTable.tsx` — drop `200_000` literal, use `c.context_window_size`
  - `web/src/lib/api.ts` — add `context_window_size?: number` to the change type
- **Specs:**
  - `openspec/specs/context-window-metrics/spec.md` — modified delta
- **Run-report templates:** wherever the "CONTEXT WINDOW OVERFLOW" finding is emitted (search needed during apply phase)
- **Backwards compat:** The state field names stay the same (`context_tokens_start`, `context_tokens_end`), so the API contract for downstream consumers is preserved. Old runs without `peak_context_tokens` simply have the field unset — the UI hides it for those rows.
- **No external API changes.** No new dependencies. No data migration needed.
