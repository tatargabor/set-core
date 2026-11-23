## Context

Two parallel event JSONL streams have coexisted in the orchestration directory since the bash→Python monitor migration. `paths.py:499-511` defines both as canonical (`events_file` returns `orchestration-events.jsonl`; `state_events_file` returns `orchestration-state-events.jsonl`). On the **write side** the two are clearly differentiated:

- The live `EventBus` (`events.py:272` derives the path from `state_file` stem → `orchestration-state-events.jsonl`) and the heartbeat / shutdown / digest emitters write to the narrow stream.
- `WATCHDOG_HEARTBEAT`, `MONITOR_HEARTBEAT`, `STATE_CHANGE`, `GATE_*`, `MERGE_*`, `LLM_CALL`, `ITERATION_END`, `AGENT_SESSION_DECISION`, and the bulk of run-time events end up in the LIVE `orchestration-events.jsonl` stream — populated either by the supervisor's separate emitter or by direct file appends in the engine/merger.

The **read side** has not kept pace:

- `_api_old.py:1644` opens only the narrow stream for the `/api/{project}/events` endpoint.
- `state.py:1259-1277` derives its events path the same way for `reconstruct_state_from_events`.
- A few sites already read both correctly: `_api_old.py:2819` (forensics/event-archive), `forensics/orchestration.py:110-111` (separates them by purpose), `bin/set-merge:147-148` (cleanup enumerates both).

The history hint comes from `tests/e2e/runs/craftbrew-findings.md #2` (the original "events filename mismatch" bug): a previous fix derived the events filename from `STATE_FILENAME` so the bash sentinel and the orchestrator agreed. That fix was correct at the time, but since then the supervisor/heartbeat/state-change emit machinery was wired to the OTHER file, leaving the API reader anchored to the now-narrower stream.

Empirical evidence (extracted from the two recent micro-web runs):

| Run | Live stream events | Narrow stream events | API `/events` returned |
|---|---|---|---|
| 1805 (12/12 merged) | ~5,500 (incl. 15 STATE_CHANGE) | 3 (DIGEST only) | `[]` (effectively) |
| 0245 (6/9 merged) | 6,066 (incl. 9 STATE_CHANGE) | 7 (DIGEST + SHUTDOWN) | `[]` |

For the redispatch counter: the same two runs show three changes (`cmdk-and-mobile-nav-e2e`, `blog-list-with-filter`, `navigation-chrome`) where `STATE_CHANGE: integration-e2e-failed → running` is in the events stream and the agent did re-execute (5+5 `ITERATION_END` events), yet `redispatch_count=0` in the API. The merger uses `extras["integration_e2e_retry_count"]` for its bound check (default 3 retries, see `merger.py:1697 DEFAULT_E2E_RETRY_LIMIT`); that counter increments correctly but never surfaces to the read side.

## Goals / Non-Goals

**Goals:**

- The dashboard's timeline tab returns the live event stream when the project has one, with no client-side change.
- `reconstruct_state_from_events` recovers the same `STATE_CHANGE` history the live stream actually contains, fixing the part of `Run #19 Bug #50` that's caused by reading the wrong file.
- API consumers see a top-level `integration_retry_count` per change, accurately reflecting merger-driven re-dispatch cycles.
- Write paths and event-bus contracts are untouched. Anyone emitting today keeps emitting to the same place.

**Non-Goals:**

- No coverage audit of `update_change_field` callers (the OTHER half of `Run #19 Bug #50` — that the engine's status mutations don't pass `event_bus`). Doing both at once collides with the just-landed model-config-unified refactor; this change is the read-side fix only.
- No `VERIFY_GATE` payload audit (empty `gate=""` `result=""` events). Separate change — touches `verifier.py` which model-config-unified just modified in 6+ places.
- No `LLM_CALL elapsed_ms` fix. Same conflict-avoidance reasoning.
- No frontend change. The dashboard renders whatever the API gives; surfacing `integration_retry_count` in a column is a follow-up UX touch.
- No event-stream consolidation on the WRITE side. Two writers continue; the divergence is a separate refactor for a future change once the model-config dust settles.

## Decisions

### D1 — Reader prefers the live stream, narrow stream as fallback

For both `/api/{project}/events` and `reconstruct_state_from_events`, the resolution chain becomes:

1. `<project>/orchestration-events.jsonl` (live stream)
2. `<project>/orchestration-state-events.jsonl` (narrow stream — back-compat)
3. `<project>/set/orchestration/orchestration-events.jsonl` (legacy nested location)
4. `<project>/set/orchestration/orchestration-state-events.jsonl` (legacy nested narrow)

Returns the FIRST file that exists. Does not merge. Rationale: merging streams is correctness-risky (interleaving timestamps from independent emitters can mis-order events); since the narrow stream is mostly DIGEST/SHUTDOWN milestones already represented in the live stream by adjacent `MEMORY_HYGIENE`/`SHUTDOWN_*` events, picking one wins on simplicity.

**Alternative considered**: merge both streams sorted by timestamp. Rejected — the narrow stream's events are operationally coarse (digest start/complete, shutdown) and a subset of what the live stream already conveys via `STATE_CHANGE` and lifecycle events. The merge cost (sort + dedupe) and the risk of timestamp skew between two writers outweigh the marginal information gain.

**Alternative considered**: the API reader merges both, with explicit dedupe by `(timestamp, type, change)`. Rejected for the same reasons — the operational value of the narrow stream is in forensics, not live UI, and forensics already reads both via `_api_old.py:2819`.

### D2 — Rotated cycles are honored on the live stream

`paths.py:514` already exposes `rotated_event_files` (the `orchestration-events-cycle*.jsonl` siblings sorted by cycle). The `/api/{project}/events` endpoint SHALL include rotated cycles in chronological order before the live tail when the live file alone is insufficient (i.e. truncated by rotation).

Concretely: when the limit is `N` and the live tail has `M < N` events, the endpoint reads the most recent rotated cycle(s) for the remainder. This avoids returning a partial slice when the operator wanted the most recent N events across rotation boundaries.

**Implementation note**: this is an additive behavior — the existing tail-N implementation works on a single file today. The rotation-aware version reads the live file last and prepends rotated content as needed, capped at `limit`.

### D3 — `integration_retry_count` is a read-time alias of `extras["integration_e2e_retry_count"]`

The Change dataclass keeps its current field set (no schema migration). The API serializer (the function that builds the per-change dict for `/api/{project}/changes` and `/api/{project}/changes/{name}`) computes `integration_retry_count = change.extras.get("integration_e2e_retry_count", 0)` and includes it as a top-level field next to `redispatch_count`.

**Naming rationale**: the extras key is named `integration_e2e_retry_count` because the historical merger code only re-dispatched on integration-e2e fails. The same counter is now also bumped by the integration-test fail path (`merger.py:1882`) and the integration-coverage fail path (`merger.py:2401`). The name `integration_retry_count` (without the `_e2e_` infix) reflects the broader current usage and is what the API exposes; the underlying extras key stays unchanged for back-compat.

**Alternative considered**: promote `integration_retry_count` to a first-class `Change` dataclass field, write through state migration. Rejected — adds schema-migration risk, blocks model-config-unified consumers if their state files lag, and the read-only alias serves the same observability purpose with zero blast radius.

### D4 — Documentation lives next to the code

`paths.py:499-511` gets a 2-line docstring on each property explaining who reads what. No README change is required because the operator-visible contract is the API endpoint, which now does the right thing without explanation.

A one-paragraph note in `docs/howitworks/en/06-monitor-and-watchdog.md` (or wherever event sources are described) is OPTIONAL — add only if a quick read shows the existing prose now contradicts the new reader behavior.

## Risks / Trade-offs

- **Reader behavior change for projects that rely on the narrow stream**. Forensics tools and `bin/set-merge:147-148` enumerate both files explicitly and don't touch the API endpoint, so they are unaffected. The migration script `migrations/backfill_lineage.py:101` reads the narrow stream — verify it still gets the events it cares about (DIGEST_*) by inspection.
- **Mitigation**: the fallback chain (D1) preserves the OLD behavior for any project whose live stream is absent. The change is a strict superset of what the API returned before.
- **Rotated-cycle inclusion (D2) increases payload size on rotation-heavy projects**. With `limit=500` (default) the cap still binds; only the SOURCES change, not the size. If a project has frequent rotation and short cycles, the operator may briefly see events from the previous cycle in the timeline. This is the desired behavior, not a regression.
- **`integration_retry_count` is an aliased read** — if a future refactor renames the extras key, the alias must be updated in lockstep. Mitigation: a unit test asserts both names produce the same value.
- **No state migration**. Old runs whose state file lacks `extras["integration_e2e_retry_count"]` will return `0` for `integration_retry_count`. This is correct — those runs really had `0` integration retries known to the system, since the counter didn't exist before its own introduction.

## Migration Plan

1. Add the resolver chain in `_api_old.py::get_events` (live → narrow → legacy nested live → legacy nested narrow). Test with both runs (1805 and 0245) — expect non-empty event lists.
2. Add the same resolver chain in `state.py::reconstruct_state_from_events`. Test by pointing it at the 1805 run state + events and confirming the reconstructed state has the same `STATE_CHANGE`-derived statuses as the live state file.
3. Add `integration_retry_count` to the per-change API serializer. Test on the navigation-chrome change of run 0245 — expect a non-zero value.
4. Add rotated-cycle inclusion to `/api/{project}/events`. Test on a project with at least one rotated cycle file (any longer-running consumer project — gitchen has 6 merged changes and likely has cycle rotation).
5. Update `paths.py` docstrings.
6. Run the full unit suite. No existing unit tests should break — the change is additive.
7. Manually exercise the dashboard against the 1805 run via `localhost:7400` and confirm timeline tab is populated.

**Rollback**: revert the commit. No state-shape or write-path changes; rollback is purely cosmetic on the read side.

## Open Questions

- **Should `reconstruct_state_from_events` also enumerate rotated cycles?** The current implementation reads a single file. If a project crashed deep into a long run and rotated several times, only the active cycle's events would be replayed — losing any `STATE_CHANGE` from earlier cycles. **Tentative answer**: yes, but as a follow-up. The defect we're fixing is "the right CURRENT file" — extending to the rotation history is incremental and can be a separate small change once we verify the basic fix works. Tasks include a TODO comment for this.
- **Should the narrow stream be deprecated entirely?** Long-term yes — having two writers is the original sin. Short-term no, because the bash side (`bin/set-orchestrate:560,593`, `bin/set-merge:147,148`) and `migrations/backfill_lineage.py` all reference it, and untangling those is a meaningful refactor. Park this for a `event-stream-consolidation` change after the model-config dust settles.
- **Should `redispatch_count` be deprecated in favor of a single `total_retry_count` summing planner + integration retries?** Tempting but rejected for this change — the two retry types have different semantics (planner-driven failure-pattern recovery vs merger-driven post-integration retry) and operators may want to distinguish. Surfacing both fields gives that option without forcing it.
