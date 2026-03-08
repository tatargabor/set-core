## Context

The token pipeline currently reduces rich 4-type data to a single integer at the earliest stage (`get_current_tokens()` extracts only `.total_tokens` from `wt-usage` JSON). All downstream consumers (loop-state, orchestration-state, e2e-report) only see this single number.

The data source (`wt-usage --format json`) already emits: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`. No changes to wt-usage or UsageCalculator are needed.

## Goals / Non-Goals

**Goals:**
- Propagate all 4 token types through the pipeline
- Show breakdown in e2e-report (summary + per-change)
- Backward compatible: new fields default to 0, existing `total_tokens`/`tokens_used` fields unchanged

**Non-Goals:**
- Per-model breakdown in reports (future work)
- Changing cost estimation logic
- Per-iteration breakdown in reports (data stored but not displayed)

## Decisions

### D1: Return format for get_current_tokens()

**Decision:** Return a JSON string instead of a plain integer. Callers parse with jq.

**Why:** Returning 4 separate values from a bash function is awkward (echo + positional parsing, or env vars). A JSON string like `{"in":X,"out":Y,"cr":Z,"cc":W,"total":T}` is clean, parseable with jq, and extensible.

**Alternative considered:** 4 separate functions (`get_current_input_tokens`, etc.) — rejected, 4x the wt-usage calls.

**Alternative considered:** Global variables — rejected, fragile and hard to trace.

### D2: Delta calculation approach

**Decision:** Compute per-type deltas individually: `in_delta = in_after - in_before`, etc.

Each type is monotonically increasing within a session, so subtraction works correctly. The total delta is the sum of type deltas (or can be derived from `total_after - total_before` as before for cross-validation).

### D3: State file field naming

**Decision:** Use short, consistent prefixes in JSON state files:

```
loop-state.json:
  "total_tokens": N          (unchanged — backward compat)
  "total_input_tokens": N    (new)
  "total_output_tokens": N   (new)
  "total_cache_read": N      (new)
  "total_cache_create": N    (new)

  iterations[].tokens_used: N        (unchanged)
  iterations[].input_tokens: N       (new)
  iterations[].output_tokens: N      (new)
  iterations[].cache_read_tokens: N  (new)
  iterations[].cache_create_tokens: N (new)

orchestration-state.json:
  changes[].tokens_used: N           (unchanged)
  changes[].input_tokens: N          (new)
  changes[].output_tokens: N         (new)
  changes[].cache_read_tokens: N     (new)
  changes[].cache_create_tokens: N   (new)
```

### D4: Report format

**Decision:** Both summary and per-change tables show breakdown.

Summary:
```
| Metric        | Value                            |
|---------------|----------------------------------|
| Total Tokens  | 456K (456000)                    |
| Input         | 120K fresh + 280K cache read     |
| Output        | 45K                              |
| Cache Create  | 11K                              |
```

Per-change:
```
| Change   | Status | In    | Out  | Cache R | Cache C | Total | Dur  | Iter |
```

## Risks / Trade-offs

- **[Risk] Estimation fallback returns only total** → When `wt-usage` unavailable and `estimate_tokens_from_files()` kicks in, we only get a total byte estimate. Mitigation: set type fields to 0 and mark `tokens_estimated: true` as today. Acceptable — this is a rare fallback.

- **[Risk] Wider per-change table may wrap** → 9 columns is wide. Mitigation: use short headers (In, Out, CR, CC) and K/M formatting.

## Open Questions

None — this is a straightforward data propagation change.
