## Context

The orchestrator runs an extensible quality-gate pipeline whose membership is defined by the active project profile. The profile abstraction (`gate-registry` capability) is already mature: `ProjectType.register_gates() -> list[GateDefinition]` in `lib/set_orch/profile_types.py:721`, with concrete implementations in `lib/set_orch/verifier.py:_get_universal_gates()` (8 universal gates) and per-module overrides like `WebProjectType.register_gates()` (5 web gates: `i18n_check`, `e2e`, `lint`, `design-fidelity`, `required-components`) at `modules/web/set_project_web/project_type.py:1263`. Mobile adds `xcode-build`. Every `GateDefinition` already carries `name`, `position`, `phase`, per-change-type `defaults`, `result_fields`, and `run_on_integration` flags. `gate_retry_policy()` declares per-gate retry mode (`always`/`cached`/`scoped`).

The web dashboard (`web/`) does not consume any of this. Five rendering surfaces hardcode a 6-gate subset: `LogPanel.buildGateTabs` (5 sub-tabs), `ChangeTable.hasGates` and `<GateBar>` props (6 fields), `GateBar.gateLabels` and the `gates` array (6 items), `GateDetail.gates` (6 entries), `PhaseView` (re-mounts `<GateBar>`). The DAG was partially fixed in `0f3556a1` to honor 11 gate kinds dynamically from the journal, but `GateKind` is still a fixed literal union and three backend gates (`design-fidelity`, `required-components`, `xcode-build`) are absent.

The retry-reason heuristic in `web/src/lib/dag/journalToAttemptGraph.ts:closeAttemptOnRetry` falls through to `'unknown'` whenever the failed attempt has no node it recognizes — exactly the case when a gate it does not know failed. Meanwhile the backend already knows the cause: `GateResult.terminal_reason` (e.g., `"max_turns"`, `"timeout"`), and the `<session_id>.verdict.json` sidecar (`lib/set_orch/gate_verdict.py`) records `verdict`, `source` (`fast_path`/`classifier_confirmed`/`classifier_override`/`classifier_downgrade`/`classifier_failed`), `summary`, severity counts, and structured findings.

`ff859a9d feat(observability): unify events file resolver + VERIFY_GATE schema` shipped in May 2026 as the upstream prerequisite. All 4 verifier-side and 8 merger-side `VERIFY_GATE` emit sites now write top-level `gate` and `result` keys, and `/api/{project}/events` resolves the live stream over the narrow milestones file. Capability specs `events-api` and `verify-gate-event-schema` were created in change `observability-event-file-unification`. This change builds on top of those — it does not duplicate the read-side fixes, it consumes them.

Constraints that shape decisions:

- **Layered architecture (`.claude/rules/modular-architecture.md`)**: Layer 1 (`lib/set_orch/`) must remain abstract; the registry endpoint cannot enumerate web/mobile gates explicitly.
- **Logging mandate (`.claude/rules/code-quality.md`)**: any new Python module logs registry assembly at DEBUG, endpoint hits at INFO, fallbacks at WARNING.
- **OpenSpec artifact rules (`.claude/rules/openspec-artifacts.md`)**: no project-specific names, no absolute deployment paths in artifacts.
- **No emojis in code**: existing files use `✓`/`✗`/`–` glyphs; preserve but do not introduce more.

## Goals / Non-Goals

**Goals:**

- All gates returned by `profile.register_gates() + _get_universal_gates()` render in every gate-displaying surface (Changes tab badges, LOG tab sub-tabs, GateDetail panel, DAG nodes) without per-gate frontend code.
- Adding a synthetic gate to a profile's `register_gates()` is sufficient to make it appear in the dashboard — no `GateKind` literal edit, no `gateLabels` map edit, no `buildGateTabs` array edit.
- Retried attempts always show *which* gate failed and *why* in the GUI when the backend has that information; the heuristic `'unknown'` fallback fires only when the journal genuinely lacks data.
- Treat the existing `gate-registry` (backend abstraction) and `observability-event-file-unification` (events resolver + VERIFY_GATE schema) as upstream prerequisites; build on them, do not redo them.

**Non-Goals:**

- Modifying gate execution behavior (no changes to which gates run, what they assert, or their ordering).
- Redesigning visual styling, DAG layout, or LogPanel UX beyond the dynamic-list refactor.
- Mobile-dashboard polish beyond `xcode-build` becoming visible via the dynamic registry.
- Backwards compatibility with the typed `*_result` / `*_output` / `gate_*_ms` fields on `ChangeInfo` after the migration period — they coexist during transition then can be retired.
- Re-spec'ing the VERIFY_GATE event schema or events-file resolution (already covered by `verify-gate-event-schema` and `events-api`).

## Decisions

### Decision 1: New project-scoped registry endpoint, not global

**Choice**: `GET /api/{project}/gates/registry` returns the resolved gate list for the active profile of the named project. Response includes `gates: [{name, label, phase, position, run_on_integration, retry_policy, change_type_defaults}, …]`.

**Rationale**: Different projects can use different profiles (web, mobile, future python). A project-scoped endpoint mirrors `/api/{project}/changes`, `/api/{project}/events`, `/api/{project}/timeline`. A global endpoint would force the dashboard to assume profile uniformity, which the modular architecture explicitly does not.

**Alternative considered**: a global `/api/gates/registry` returning a union of all installed profiles. Rejected because it leaks profile-irrelevant gates into per-project views (e.g., showing `xcode-build` in a web project).

### Decision 2: Generic `gates: Record<string, GatePayload>` map on `ChangeInfo`, additive to existing typed fields

**Choice**: extend `ChangeInfo` with a new optional `gates` field carrying `{result, output, ms, terminal_reason?, verdict_source?, verdict_summary?}` keyed by gate name. Keep existing `*_result` / `*_output` / `gate_*_ms` typed fields populated for the transition; new code reads `gates[name]` first and falls back to the typed field.

**Rationale**: Honest representation of an open-ended set. Frontend code that needs to enumerate gates iterates `Object.keys(change.gates ?? {})` joined with the registry response. Typed-field consumers (sentinel UI, learnings) keep working unchanged.

**Alternative considered**: replace typed fields wholesale with the generic map. Rejected because it forces every consumer to migrate in lockstep, expanding blast radius beyond this change.

### Decision 3: Widen `GateKind` from literal union to `string` alias

**Choice**: `export type GateKind = string` with a documentation comment naming the well-known kinds (`build`, `test`, `e2e`, …) plus `impl` and `terminal`. Drop `GATE_KINDS` allow-list filtering in `journalToAttemptGraph` — accept any non-empty string from the journal.

**Rationale**: A registry-driven model means any profile-registered name is valid. Keeping the literal union forces a manual edit per new gate, which is the exact regression `0f3556a1` had to fix retroactively. Type-checking still catches typos at usage sites because consumers reference well-known constants.

**Alternative considered**: keep literal union, regenerate from registry at build time via codegen. Rejected because it adds a build-time dependency on a running backend or a checked-in JSON snapshot that drifts.

### Decision 4: Surface `terminal_reason` and verdict-sidecar fields via the journal/changes API, not a separate endpoint

**Choice**: Each per-gate entry in the journal/changes response gains optional `terminal_reason`, `verdict_source`, `verdict_summary` fields. Backend reads `GateResult.terminal_reason` from state and the `<session_id>.verdict.json` sidecar via `read_verdict_sidecar` from `gate_verdict.py`.

**Rationale**: The data is already attached to a specific gate run; the natural carrier is the journal entry that already carries the gate's `result` and `output`. A separate `/verdicts` endpoint would force the frontend to do a join. The fields are additive and optional — pre-`ff859a9d` data simply lacks them.

**Alternative considered**: add a `/api/{project}/changes/{name}/verdicts` endpoint. Rejected as redundant given the journal already has the relationship.

### Decision 5: Retry-reason composition uses the new fields, with `'unknown'` reserved for genuinely missing data

**Choice**: Frontend `closeAttemptOnRetry` updated to:

1. If the closing attempt has a node with `result === 'fail'` and that node has `terminal_reason`, render `"<gate>: <terminal_reason>"`.
2. Else if any node failed, render `"<gate>: gate-fail"` (current heuristic, but named).
3. Else if a `merge` node failed, render `"merge-conflict"` (current).
4. Else fall back to `'unknown'` — log a console.warn so future drift is visible.

**Rationale**: The user-facing problem is that *the cause exists in the data but we drop it*. Prioritizing `terminal_reason` and the failing gate's name fixes the symptom; the fall-through stays only as a last resort.

### Decision 6: Build the dashboard against the registry endpoint with a graceful fallback

**Choice**: `web/src/lib/api.ts` adds `getGateRegistry(project): Promise<GateRegistryEntry[]>`. The dashboard fetches it on project load, caches in React context, and joins with per-change `gates` map at render time. If the registry endpoint is unavailable (older backend), the dashboard falls back to the keys present on `change.gates ?? {}` with default labels (gate name in title-case).

**Rationale**: Older backends still get *some* dynamism (whatever appears in `gates` renders), avoiding a hard version coupling. New backends get the full label/phase/position metadata for ordered, well-labeled rendering.

## Risks / Trade-offs

- **Risk**: removing the `GATE_KINDS` allow-list could surface garbage strings as fake gates if the journal contains corrupt entries → **Mitigation**: ignore empty strings and reserved kinds (`impl`, `terminal`); log a `console.warn` for any kind not in the registry response so drift is visible; do not break rendering on unknowns.
- **Risk**: refactoring 5 frontend rendering sites in one change is a wide blast radius → **Mitigation**: introduce one shared `useGateRegistry()` hook + one `GateView` primitive that all five sites consume; the diff is concentrated in one place. Existing E2E tests cover the surfaces; extend them as the implementer migrates each site.
- **Risk**: the registry endpoint depends on profile loading, which may fail for misconfigured projects → **Mitigation**: graceful degradation — the endpoint returns 200 with `gates: []` and a `warning` field, never 500. Frontend's fallback path renders whatever appears in `change.gates`.
- **Risk**: `terminal_reason` and verdict-sidecar fields are missing for pre-`ff859a9d` runs → **Mitigation**: explicit acceptance that the `'unknown'` fall-through still fires for legacy data; new runs get the named cause.
- **Trade-off**: keeping typed `*_result` fields alongside the generic `gates` map increases `ChangeInfo` payload size and provides two ways to read the same data. Acceptable for the migration period; can be retired in a follow-up after consumers migrate.
- **Trade-off**: widening `GateKind` to `string` loses type-checking for typos at the kind level. Mitigated by gate-name constants in the registry response (the source of truth) — code that hardcodes a name is doing it wrong by construction.
