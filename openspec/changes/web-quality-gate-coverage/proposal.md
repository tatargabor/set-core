## Why

The web dashboard renders only a hardcoded 6-gate subset of the quality-gate pipeline that the orchestrator actually runs, so attempts that fail on a newer gate (`design-fidelity`, `required-components`, `i18n_check`, `lint`, `scope_check`, `rules`, `test_files`, `e2e_coverage`, `spec_verify`, or `xcode-build`) show as retried with a generic `unknown` reason. Every backend gate addition requires manual edits in five-plus frontend files; that sync step keeps getting forgotten and the GUI silently drifts out of date with the engine.

## What Changes

- **NEW** backend HTTP endpoint that returns the resolved per-profile gate registry (name, label, phase, position, retry policy, integration flag) so clients can render gates dynamically instead of hardcoding lists.
- **NEW** journal/changes API surfacing of `terminal_reason` and verdict-sidecar fields (`source`, `summary`) so the GUI can name the failure cause for retried attempts.
- **MODIFIED** frontend gate-rendering: replace hardcoded gate lists in `LogPanel.buildGateTabs`, `ChangeTable` `hasGates` + `<GateBar>` props, `GateBar.gateLabels` + `gates` array, `GateDetail.gates`, and `PhaseView` with registry-driven dynamic rendering. Drop the `SubTab` literal union in `LogPanel`.
- **MODIFIED** `GateKind` type (and `GATE_KINDS` allow-list, `enrichWithSessions.labelToGateKind`) to widen from a fixed literal union to an open `string` so any profile-registered gate is honored without a frontend change.
- **MODIFIED** `ChangeInfo` (`web/src/lib/api.ts`) to add a generic `gates: Record<string, {result, output, ms}>` map alongside the existing typed per-gate fields, providing a forward-compatible carrier for new gates.
- **MODIFIED** retry-reason derivation (`closeAttemptOnRetry`) to read the failing gate name and `terminal_reason`/verdict source from the journal events and surface them in the DAG retry-edge tooltip and linear-view retry cell — never `unknown` when the backend emitted a cause.
- **NEW** web E2E test asserting that all profile-registered gates appear in the LOG tab sub-tabs, GateDetail, and Changes-tab GateBar against a fixture project that exercised the newer gates.

This is **not** a redesign of gate execution, the DAG layout, or LogPanel UX — only a registry-driven refactor of how the GUI consumes the gate list and failure reasons.

## Capabilities

### New Capabilities
- `gate-registry-api`: HTTP surface that exposes the resolved per-profile gate registry (gate definitions + retry policy + integration flags) to web clients, with metadata sufficient for dynamic rendering.
- `web-dashboard-gate-rendering`: web GUI rendering contract for quality gates — Changes tab badges, LOG tab sub-tabs, GateDetail panel, and DAG nodes are driven by the gate-registry-api response, not hardcoded gate lists.

### Modified Capabilities
- `gate-observability`: extend with the requirement that per-gate failure reasons (`terminal_reason`, verdict-sidecar `source`, `summary`) are surfaced in the journal/changes API response so consumers can name the cause of a retry.

## Impact

- **Backend**: new endpoint module under `lib/set_orch/api/orchestration.py` (or sibling); reads from `profile.register_gates() + _get_universal_gates()` and `profile.gate_retry_policy()`; writes nothing. Journal/changes responses gain new fields (`terminal_reason`, `verdict_source`, `verdict_summary`) on a per-gate basis. No event-bus or state-mutation contract changes.
- **Backend (mobile)**: `xcode-build` gate (`modules/mobile/set_project_mobile/gates.py`) verified to be returned by `MobileProjectType.register_gates()` so the registry endpoint includes it.
- **Frontend (`web/`)**: refactors in `LogPanel.tsx`, `ChangeTable.tsx`, `GateBar.tsx`, `GateDetail.tsx`, `PhaseView.tsx`, `lib/dag/types.ts`, `lib/dag/journalToAttemptGraph.ts`, `lib/dag/enrichWithSessions.ts`, `lib/api.ts`. Visual styling unchanged.
- **Tests**: extend `web/tests/unit/journalToAttemptGraph.test.ts` for the new gate kinds and the retry-reason surfacing; new Playwright case under `web/tests/e2e/`.
- **Specs**: builds on `gate-registry` (existing backend abstraction) and `observability-event-file-unification` (upstream — already shipped the VERIFY_GATE schema and events resolver). Does not duplicate either.
- **Backwards compatibility**: existing typed `*_result` / `*_output` / `gate_*_ms` fields on `ChangeInfo` are preserved during the transition; new `gates` map is additive. Old hardcoded UI mounts are removed in the same change because internal API.
- **No breaking changes** to gate execution, event schema, or external integrations.

## Scope Considerations (parked for re-evaluation before /opsx:apply)

The proposal as written is the "right engineering answer" but may be larger than the user's literal complaint requires. Before implementing, decide between **full** and **slim** versions:

### The user's actual complaint

1. Retry shows `unknown` reason on the Changes tab.
2. Newer gates (`design-fidelity`, `required-components`, etc.) are missing from the DAG and LOG views.

### The four solution layers

- **Layer 1 — Frontend dynamic rendering (required)**: drop hardcoded gate lists in `LogPanel.buildGateTabs`, `ChangeTable`, `GateBar`, `GateDetail`, `PhaseView`. Drive from `Object.keys(journal.grouped ?? {})` joined with whatever gate-result fields are present on the change object. Widen `GateKind` to `string`, drop `GATE_KINDS` allow-list filtering. — Closes complaint #2 entirely.
- **Layer 2 — Retry-reason naming (required)**: update `closeAttemptOnRetry` to render `"<gate>: gate-fail"` instead of bare `"unknown"` whenever any node failed. — Closes complaint #1 entirely.
- **Layer 3 — `terminal_reason` + verdict-sidecar surface (nice-to-have)**: small backend addition that lets the GUI render `"spec_verify: max_turns"` instead of `"spec_verify: gate-fail"`. Polish, not required for the user's complaint.
- **Layer 4 — Backend `gates/registry` HTTP endpoint + React `GateRegistryContext` + fallback path (deferred)**: future-proofs against registry drift, lets the GUI show "this gate WILL run" before any gate has executed, supplies labels and ordering metadata. The user did not complain about empty-state visibility; the journal already provides every gate that ran for a change. Significant blast radius, ~2–3 days of work.

### Recommended slim version (Layers 1+2+3, drop Layer 4)

Keep the `gate-observability` delta spec (Layer 3). Replace the new `gate-registry-api` capability with a `web-dashboard-gate-rendering` capability whose requirements are journal-driven, not registry-driven. Drop:

- The `getGateRegistry()` API client wrapper.
- The `GateRegistryContext` provider and `useGateRegistry()` hook.
- The generic `gates: Record<string, GatePayload>` map on `ChangeInfo` — the journal carries this data already; new typed fields on `ChangeInfo` cover what the Changes-tab badges need before journal data loads.
- The "fallback when registry endpoint is unavailable" requirement (no endpoint to be unavailable).

Estimated reduction: 30 tasks → ~12 tasks; 6 frontend files → still ~6 files but each with a much smaller diff; no new backend endpoint.

### When the full version is the right call

Add Layer 4 if and only if: (a) operators want to see "this change WILL run lint" before lint runs, (b) gate ordering in the GUI must match the pipeline order even before any gate has executed, or (c) per-gate retry-policy / change_type-defaults metadata is needed for a feature beyond rendering.

### Current state

Both versions are valid. The artifacts as written reflect the full version. Re-evaluate before running `/opsx:apply`; if going slim, regenerate `specs/` and `tasks.md` for the trimmed scope and archive the dropped `gate-registry-api` capability proposal as a follow-up change idea.
