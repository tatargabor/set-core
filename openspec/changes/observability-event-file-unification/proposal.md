## Why

Two observability defects make the web dashboard's timeline tab effectively blind to live runs and the per-change retry metric misleading. Both were diagnosed from the actual events.jsonl + API response of two recent micro-web runs (2026-05-01-1805 with 12/12 merged, and 2026-05-02-0245 with 6/9 merged before SIGTERM).

### Defect 1 — `/api/{project}/events` reads the wrong file

`paths.py` defines two parallel event streams:

- `orchestration-events.jsonl` (the **live** stream — 446–578 KB, 5,500–6,066 events per run, populated with `STATE_CHANGE`, `GATE_PASS`, `GATE_START`, `MERGE_*`, `LLM_CALL`, `ITERATION_END`, `WATCHDOG_HEARTBEAT`, etc.)
- `orchestration-state-events.jsonl` (a **narrow** stream — 280–808 bytes, 3–7 events per run, populated only by `MEMORY_HYGIENE`, `DIGEST_*`, `SHUTDOWN_*`, `CHANGE_STOPPING`, `CHANGE_STOPPED`)

`api/orchestration.py:993` `/api/{project}/events` reads only the second file, falls back to a `set/orchestration/` legacy location of the same narrow file, and returns `{"events": []}` when neither resolves. As a result:

- The dashboard timeline tab sees zero events even though the live stream has thousands.
- `state.py:1259 reconstruct_state_from_events` derives its path the same way and reads the narrow stream — explaining why `Run #19 Bug #50` (state reconstruction loses merged status) reproduces with the Python monitor: the relevant `STATE_CHANGE` events live in the OTHER file the reconstruct logic never opens.
- Operators looking at the dashboard for "what just happened" cannot diagnose retries, gate failures, or merge progress.

### Defect 2 — `VERIFY_GATE` event payload schema is inconsistent across emit sites

The `VERIFY_GATE` event has 12 emit sites — 4 in `verifier.py` (verify-pipeline retry/failed/pass paths and the uncommitted-work check) and 8 in `merger.py` (integration-phase gate fail/skip/pass paths). The two source files use **different field schemas** for the same event type:

| Site | `gate` field | `result` field | Notes |
|---|---|---|---|
| `merger.py:1793,1851,1860,1868,2022,2195,2269,2407` | yes (`"build"`, `"e2e"`, `"e2e-smoke"`, …) | yes (`"fail"`, `"skip"`) | Consumer-friendly |
| `verifier.py:4062` (uncommitted check) | NO | yes (`"fail"`) | Missing `gate` |
| `verifier.py:4349` (retry path) | NO — uses `"stop_gate"` instead | yes (`"retry"`) | Different key name |
| `verifier.py:4372` (failed path) | NO — uses `"stop_gate"` instead | yes (`"failed"`) | Different key name |
| `verifier.py:4455` (pass path) | NO | NO | Schema-distinct: spreads `**summary` instead |

Concrete impact: in the 1805 run, 14 of 18 `VERIFY_GATE` events return `data.get("gate") == ""` and `data.get("result") == ""` to a consumer that uses these field names (the dashboard parsing exhibited this). The data ISN'T missing — it's under different keys (`stop_gate`, or as a key spread inside the dict). This makes per-gate analysis on the API consumer side fragile and asymmetric between integration-phase and verify-phase events.

## What Changes

- **`/api/{project}/events`** SHALL read the live `orchestration-events.jsonl` stream (and rotated cycles), with a documented fallback to `orchestration-state-events.jsonl` only when the live stream is absent. Filtering and limit semantics are preserved.
- **`VERIFY_GATE` event payload schema** SHALL be consistent across all 12 emit sites: every emit MUST include `"gate": <gate_name_or_empty>` and `"result": <"pass"|"fail"|"retry"|"failed"|"skip">` keys at the data dict's top level. Existing `"stop_gate"` fields are kept (back-compat) but the new `"gate"` key is added alongside.
- **`reconstruct_state_from_events`** in `state.py` SHALL prefer the live stream as well — single canonical source so post-crash state recovery sees the full `STATE_CHANGE` history that other recent fixes already emit there.
- **No write-side changes** to event-bus contracts or state-mutation flow. Only the schema of one event TYPE (`VERIFY_GATE`) is unified, and only the read-side resolves the right file.
- **No `Change` serializer change.** Investigation showed that `extras["integration_retry_count"]` and `extras["integration_e2e_retry_count"]` are ALREADY exposed at the API top level via `Change.to_dict()`'s `d.update(self.extras)` spread (state.py:436). Surfacing/renaming them is a frontend concern that belongs to the separate `web-quality-gate-coverage` change.
- **Documentation only**: a one-line note in `paths.py` stating which stream is the canonical reader source and that the narrow stream is retained for shutdown/digest milestones.

## Capabilities

### New Capabilities

- `events-api`: The `/api/{project}/events` endpoint and `reconstruct_state_from_events` agree on the canonical event stream (`orchestration-events.jsonl` + rotated cycles), with a documented fallback chain.
- `verify-gate-event-schema`: All 12 `VERIFY_GATE` emit sites use a consistent payload schema with `gate` and `result` keys at the top level, regardless of source file (verifier vs merger) or path (retry / failed / pass / uncommitted / integration-fail / etc.).

### Modified Capabilities

- None. This change is additive on the read path; no existing capability behavior is removed or repurposed.

## Impact

- **Affected files (Layer 1 only)**:
  - `lib/set_orch/api/orchestration.py` — `/api/{project}/events` endpoint reader (line ~993) gains a 4-step file-resolver chain plus rotated-cycle inclusion.
  - `lib/set_orch/state.py` — `reconstruct_state_from_events` default `events_path` resolution gets the same chain.
  - `lib/set_orch/paths.py` — docstring clarification on `events_file` vs `state_events_file`.
  - `lib/set_orch/verifier.py` — 4 `VERIFY_GATE` emit sites (lines 4062, 4349, 4372, 4455) each gain a `"gate"` key in the data dict alongside the existing fields. The pass path also gains `"result": "pass"`.
- **No write-side changes** to event-bus mechanics or state-mutation flow.
- **No `Change` schema change.** `redispatch_count` keeps its semantic; the existing `extras["integration_e2e_retry_count"]` and `extras["integration_retry_count"]` are already in the API response via `to_dict()`'s extras spread.
- **No model-config-unified conflict**. The verifier.py edits are AT the VERIFY_GATE emit lines (4062, 4349, 4372, 4455) — model-config-unified touched verifier.py at `review_change` (line ~1426), `_execute_review_gate` (~3088), `_execute_spec_verify_gate` (~3390), `_get_universal_gates` (~3819) — disjoint regions.
- **Tests**: unit tests on the API readers using fixture event streams; reconstruction-from-live-stream test; VERIFY_GATE emit test asserting `gate` and `result` keys present in all 4 verifier paths.
- **Migration**: none. Existing runs' event files are honored as-is; the read-side simply opens the right file first. Existing `VERIFY_GATE` events in old jsonl files keep their `stop_gate` field; new emits gain the additional `gate` key.
- **Frontend**: rendering the existing extras-spread counters is the responsibility of the separate `web-quality-gate-coverage` change. This proposal ships the API + event-stream consistency so the dashboard work is unblocked.
