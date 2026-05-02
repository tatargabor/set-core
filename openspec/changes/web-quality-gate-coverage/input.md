# Brief: web-quality-gate-coverage

## Problem

The set-core web dashboard (`web/`) under-renders the quality-gate pipeline that actually runs on changes. The user-visible symptoms:

- Under the **Changes tab**, attempts visibly retry but the failure cause shows as `unknown` — the gate that triggered the retry is not named.
- The **DAG view** and **LOG tab** are missing nodes/sub-tabs for several gates entirely. They cannot drill into a failure they don't know exists.

Three independent gaps cause this. Recent commits closed PART of the problem; the rest is still open.

### What is already fixed (do not redo)

- **Backend VERIFY_GATE event schema** was unified in `ff859a9d feat(observability): unify events file resolver + VERIFY_GATE schema`. All 4 verifier-side emit sites and 8 merger-side sites now write explicit `gate` + `result` keys at the data dict top level, so consumer parsing of `data.get("gate")` no longer returns empty for the verifier paths. That commit also fixed `/api/{project}/events` to read the live event stream (`orchestration-events.jsonl`) instead of the narrow milestones file (`orchestration-state-events.jsonl`). Capability specs `events-api` and `verify-gate-event-schema` were created in change `observability-event-file-unification` and SHOULD be treated as upstream prerequisites for this change.
- **DAG view gate coverage** was partially fixed in `0f3556a1 fix(web/dag): render lint / test_files / spec_verify / i18n_check gates`. `GateKind` and `GATE_KINDS` were widened to include those 4 gate kinds, plus `enrichWithSessions.labelToGateKind` learned to map their session labels.
- **Profile-driven gate registration** is the canonical model and has its own capability spec `gate-registry`. `ProjectType.register_gates() -> list[GateDefinition]` returns the per-profile gate list at `lib/set_orch/profile_types.py:721` (base no-op) with concrete implementations in modules (`modules/web/set_project_web/project_type.py:1206-1299` returns `i18n_check`, `e2e`, `lint`, `design-fidelity`, `required-components`).

### What is still broken (this change)

1. **Frontend re-hardcodes the gate list in three more places** even though the backend is registry-driven:
   - `web/src/components/LogPanel.tsx:128-145` — `buildGateTabs()` hardcodes 5 sub-tabs (`build`, `test`, `e2e`, `review`, `smoke`). With `7ed03ec9 feat(web-ui): drop DAG click-detail panel; wire LOG tab to selected change`, the LOG tab is now the primary gate drill-down surface — yet a change that fails on `i18n_check`, `lint`, `scope_check`, `rules`, `test_files`, `e2e_coverage`, `spec_verify`, `design-fidelity`, or `required-components` shows no sub-tab for the failing gate. The `SubTab` union (`'task' | 'build' | 'test' | 'e2e' | 'review' | 'smoke' | 'merge'`) is the symptom site.
   - `web/src/components/ChangeTable.tsx:145, 194-203, 261, 308-315` — `hasGates` check and `<GateBar>` props use the same 6-gate hardcoded list. Profile gates beyond those 6 never render in the table row badges.
   - `web/src/components/GateBar.tsx:12-19, 32-39` — `gateLabels` map has 6 entries; the `gates` array fed to the badge renderer is hand-built with 6 items. The fallback `g.name.charAt(0).toUpperCase()` produces ambiguous single-letter labels for unknown gates.
   - `web/src/components/GateDetail.tsx:24-33` — expanded gate-output panel hardcodes the same 6 entries.
   - `web/src/components/PhaseView.tsx:152-159` — inherits the 6-gate `<GateBar>` limitation.

2. **Three backend gates are missing from the frontend type system entirely** (not in `GateKind` despite shipping months ago):
   - `design-fidelity` — registered by `WebProjectType` since `c156f6ff feat(design-fidelity): JSX structural parity check` (early April 2026); has had several follow-ups (`53c885cd`, `f78a78ff`, `522118da`, `efb6c102`, `fa3bb957`).
   - `required-components` — registered by `WebProjectType` since `1a215faf feat(gates): trivial-expect detection + required-components mount gate` (early April 2026).
   - `xcode-build` — registered by mobile profile since `3c74f8bf feat: add mobile (Capacitor) project type module` (Apr 2026); the `mobile-project-type` change was archived in `d9a7e312`.
   `web/src/lib/dag/types.ts:1-16` `GateKind` union and `web/src/lib/dag/journalToAttemptGraph.ts:11-25` `GATE_KINDS` allow-list both omit these three. Result: gate runs for them are dropped on ingestion in the DAG too — same root cause as the bug `0f3556a1` fixed for the other 4, just for newer gates.

3. **No gate-registry HTTP surface**: the backend has the registry data (`profile.register_gates()` + `_get_universal_gates()` + `gate_retry_policy()`) but no endpoint exposes the resolved per-profile gate list to web clients. Until this exists, the frontend cannot become dynamic — every new gate the backend ships will silently disappear from the GUI again, repeating the `0f3556a1` regression.

4. **Retry reason still falls through to "unknown"**: `web/src/lib/dag/journalToAttemptGraph.ts:129-140` `closeAttemptOnRetry()` heuristic checks the last attempt-node's failure status. When a retry was triggered by a gate the frontend doesn't know about (case 1 or 2), no failed node is present in the attempt and the heuristic falls through to `'unknown'`. The backend already emits the failing gate (`gate` field, post-`ff859a9d`) and stores `terminal_reason` on `GateResult` plus a `<session_id>.verdict.json` sidecar (`lib/set_orch/gate_verdict.py`) with `verdict`/`source`/`summary`/`critical_count`. The frontend ignores all of this.

The pattern is **registry drift**: every new backend gate requires hand-edits in 5+ frontend files, and they keep getting forgotten.

## Goal

The web GUI must accurately reflect the gates the active profile registers, without manual sync per gate. Specifically:

- All gates returned by `profile.register_gates() + _get_universal_gates()` appear in the Changes tab badges, GateBar, GateDetail, LogPanel sub-tabs, and DAG nodes.
- Adding a new gate to a profile (e.g., a future `accessibility` or `bundle-size` gate) requires **zero frontend code changes** to become visible.
- When an attempt retries, the GUI shows **which gate failed and why** — never `unknown` if the backend emitted a `gate`/`result`/`terminal_reason` for it.
- The change builds on top of `observability-event-file-unification` (read-side fix) and `gate-registry` (backend abstraction); does not duplicate either.

## Scope

### In scope

- **Backend**: add a gate-registry HTTP endpoint that returns the resolved per-profile gate list with metadata (name, label, phase, position, retry_policy, run_on_integration). Project-scoped endpoint preferred (different projects may have different profiles).
- **Backend**: surface `terminal_reason` and verdict-sidecar `source`/`summary` fields in the journal/changes API response so the frontend can name the failure cause.
- **Backend**: add `xcode-build` (mobile) and confirm `design-fidelity` + `required-components` (web) are returned by their respective `register_gates()` implementations and appear in the registry endpoint output.
- **Frontend**: replace hardcoded gate lists with registry-driven dynamic rendering in `LogPanel.buildGateTabs`, `ChangeTable` `hasGates` + `<GateBar>` prop assembly, `GateBar.gateLabels` + `gates` array, `GateDetail` `gates` array, `PhaseView`. Drop the `SubTab` literal union in `LogPanel`.
- **Frontend**: extend `GateKind` to include `design-fidelity`, `required-components`, `xcode-build` (or widen to `string` once a registry-driven model is in place); update `GATE_KINDS` allow-list accordingly; update `enrichWithSessions.labelToGateKind` for the new kinds.
- **Frontend**: extend `ChangeInfo` (`web/src/lib/api.ts`) with the missing per-gate fields *or* (preferred) introduce a generic `gates: Record<string, {result, output, ms}>` map alongside the existing typed fields with a deprecation path.
- **Frontend**: update `closeAttemptOnRetry` to read `terminal_reason` / verdict source from the journal events, and the DAG retry edge tooltip to display the failing gate name and reason (e.g., `"design-fidelity: max_turns"`).
- **Web E2E test**: add a Playwright assertion that runs against a fixture project where `design-fidelity` and `required-components` executed, asserting both appear in the LOG tab sub-tabs and the Changes tab GateBar.

### Out of scope

- Modifying gate execution behavior (no changes to what gates do, only how the GUI sees them).
- Mobile dashboard polish beyond `xcode-build` appearing via the dynamic registry.
- Redesigning the existing DAG layout, GateNode visual style, or LogPanel UX beyond the dynamic-list refactor.
- Backwards compatibility with the old hardcoded `ChangeInfo` per-gate fields — this is internal API; refactor freely after the generic map is in place.
- Re-doing what `observability-event-file-unification` already shipped (events resolver, VERIFY_GATE schema unification).

## Key files (codebase pointers)

### Backend — gate registry source of truth (existing)

- `lib/set_orch/profile_types.py:721` — `Profile.register_gates() -> list[GateDefinition]` ABC (base no-op).
- `lib/set_orch/verifier.py:3819-3859` — `_get_universal_gates()` returns the 8 universal gates.
- `modules/web/set_project_web/project_type.py:1206-1299` — `WebProjectType.register_gates()` returns `i18n_check`, `e2e`, `lint`, `design-fidelity`, `required-components`.
- `modules/web/set_project_web/project_type.py:1317-1342` — `gate_retry_policy()` per-gate retry mode (`always`/`cached`/`scoped`).
- `modules/mobile/set_project_mobile/gates.py` — `xcode-build` gate (verify class-based registration is wired into the registry).
- `lib/set_orch/gate_profiles.py` — `GateConfig` dict-based + `UNIVERSAL_DEFAULTS` per change_type.
- `lib/set_orch/gate_verdict.py` — `GateVerdict` dataclass, sidecar persisted at `<session_id>.verdict.json`. Fields: `verdict`, `source` (`classifier_confirmed`|`max_turns`|`timeout`), `summary`, `critical_count`. **Authoritative source for "why did the gate fail".**
- `lib/set_orch/api/orchestration.py` — host of the existing `/api/{project}/...` endpoints; new gate-registry endpoint goes here. `_resolve_events_file()` (added in `ff859a9d`) is a pattern to mirror for resolver chains.

### Backend — existing capability specs to delta against

- `openspec/specs/gate-registry/spec.md` — registry data model (already covers `register_gates()`, dynamic GateConfig, pipeline-from-registry). May need a delta to add the HTTP surface requirement.
- `openspec/specs/gate-observability/spec.md` — gate observability surface; may need a delta to add the per-gate failure-reason surfacing.
- `openspec/specs/verify-gate/spec.md` — verify gate behavior.

### Frontend — files that hardcode gate lists (must become dynamic)

- `web/src/lib/dag/types.ts:1-16` — `GateKind` union (currently 14 entries; missing `design-fidelity`, `required-components`, `xcode-build`).
- `web/src/lib/dag/journalToAttemptGraph.ts:11-25` — `GATE_KINDS` allow-list (mirror of GateKind minus impl/terminal).
- `web/src/lib/dag/journalToAttemptGraph.ts:129-140` — `closeAttemptOnRetry` `'unknown'` fallback.
- `web/src/lib/dag/enrichWithSessions.ts:7-23` — `labelToGateKind()` label-string matching.
- `web/src/lib/dag/layout.ts:24-30` — `RETRY_EDGE_COLORS` (per-reason). Likely fine as-is.
- `web/src/lib/api.ts:30-112` — `ChangeInfo` type. Refactor to generic `gates` map.
- `web/src/components/LogPanel.tsx:110, 128-145` — `SubTab` literal union + `buildGateTabs()` hardcoded list. **Highest-impact fix because of `7ed03ec9` making LOG the primary drill-down.**
- `web/src/components/ChangeTable.tsx:145, 194-203, 261, 308-315` — `hasGates` + `<GateBar>` props.
- `web/src/components/GateBar.tsx:12-19, 32-39` — `gateLabels` + `gates` array.
- `web/src/components/GateDetail.tsx:24-33` — hardcoded `gates: GateSection[]`.
- `web/src/components/PhaseView.tsx:152-159` — `<GateBar>` mount.
- `web/src/components/dag/GateNode.tsx:6-43` — per-result icon/color maps; per-gate is fine, no edit needed.
- `web/src/components/LearningsPanel.tsx:264-300` — already dynamic from `gate_stats.per_gate`; reference model for the dynamic rendering pattern.

### Frontend — E2E tests

- `web/tests/e2e/` — Playwright suite. Reference: `web/tests/e2e/README.md` and `CLAUDE.md` "Web Dashboard E2E Tests" section. New assertion must use a fixture project that exercised `design-fidelity` and `required-components`. The existing pattern is `E2E_PROJECT=<run-id> pnpm test:e2e`.
- `web/tests/unit/journalToAttemptGraph.test.ts` — added in `0f3556a1`; pattern to follow for the new gate kinds + retry-reason surfacing.

## Constraints

- **Layered architecture (`.claude/rules/modular-architecture.md`)**: registry endpoint lives in `lib/set_orch/api/` (Layer 1). It calls `profile.register_gates()` (Layer 1 abstraction) which dispatches to the active profile's implementation (Layer 2). Do NOT hardcode any web-specific gate name in Layer 1 code.
- **Logging mandatory (`.claude/rules/code-quality.md`)**: any new Python module SHALL `import logging; logger = logging.getLogger(__name__)`. Log registry assembly at DEBUG, endpoint hits at INFO, resolver fallbacks at WARNING.
- **No project-specific content (`.claude/rules/openspec-artifacts.md`)**: artifacts must NOT name any client/project, use absolute deployment paths, or cite specific run-ids. The bug was diagnosed against unnamed projects; describe symptoms generically.
- **All merges via gates (`.claude/rules/sentinel-autonomy.md`)**: this change merges through the integration pipeline like any other.
- **Cross-cutting checklist (`.claude/rules/cross-cutting-checklist.md`)**: `verifier.py`, `project_type.py`, `api.ts` are cross-cutting. Edits must be additive; verify no removed fields without checking other consumers (DAG, learnings, sentinel UI).
- **No emojis in code/files** unless the user explicitly asks. Some existing files use Unicode glyphs (`✓`, `✗`, `–`); preserve their usage but do not introduce new emojis.

## Acceptance signals

- All gates returned by the active profile's `register_gates() + _get_universal_gates()` appear in: Changes tab badges, LOG tab sub-tabs, GateDetail expanded view, and DAG nodes — verified for at least one fixture project that exercised `design-fidelity` and `required-components`.
- Adding a synthetic gate `accessibility` to a test profile's `register_gates()` makes it appear in all of the above with no frontend edits (unit + E2E tests cover this).
- A retry caused by `design-fidelity` failing with `terminal_reason="max_turns"` shows `"design-fidelity: max_turns"` in the DAG retry-edge tooltip and the linear view's retry-reason cell — never `unknown`.
- New web E2E test passes against a fixture project that exercised `design-fidelity` and `required-components`.
- `pnpm test:e2e` (web/) and the standard set-core unit/integration suite both pass.
- No regression in `journalToAttemptGraph.test.ts` — the existing 11-gate assertion still holds and is extended to 14+.

## Open questions for the implementer to decide

- **Generic `gates` map vs. extended per-gate fields on `ChangeInfo`**: brief recommends the generic map but flags this as a judgment call. If sentinel UI / learnings rely on specific typed fields, an additive approach with deprecation path may be safer. Decide during design.md.
- **Registry endpoint scope**: project-scoped (`/api/{project}/gates/registry`) vs. global (`/api/gates/registry`). Project-scoped is more correct (different projects → different profiles); global is simpler if the dashboard already assumes uniform profile across projects. Recommend project-scoped.
- **Mobile (`xcode-build`) treatment**: ship registry plumbing in this change so the gate appears via the dynamic list, but defer mobile-specific UI affordances. This keeps scope contained.
- **`GateKind` union: widen to `string` vs. enumerate**: a registry-driven model implies any profile-registered name is valid, so widening to `string` is honest. Keeping the literal union forces a manual edit per new gate (the very regression this change fixes). Recommend widening.

## Related (do not duplicate)

- `openspec/changes/observability-event-file-unification/` — upstream prerequisite. Shipped in `ff859a9d`. Unifies VERIFY_GATE event schema and `/api/{project}/events` resolver. Read its `proposal.md` and `specs/` for the data shape this change consumes; do not re-spec the same surface.
- `openspec/changes/design-fidelity-ui-primitive-sync/` — uncommitted sibling. Concerns the `design-fidelity` gate's behavior (primitive parity logic), not its UI rendering. Coordinate but do not modify it.
- `openspec/changes/add-client-boundary-gate/` — recent gate-addition change. Useful pattern for how new gates were introduced and what wiring was forgotten — informs the "registry drift" framing.
- `openspec/specs/gate-registry/spec.md` — existing capability spec for backend registry. Likely needs a delta to add the HTTP surface requirement.
- `openspec/specs/gate-observability/spec.md` — likely needs a delta to add the per-gate failure-reason surfacing requirement (terminal_reason + verdict.json).
