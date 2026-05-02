## 1. Backend — gate registry endpoint

- [ ] 1.1 Add `GET /api/{project}/gates/registry` handler in `lib/set_orch/api/orchestration.py` that resolves the project's profile, calls `_get_universal_gates() + profile.register_gates()`, and returns a JSON response with each gate's `name`, `label`, `phase`, `position`, `run_on_integration`, and `change_type_defaults` [REQ: registry-endpoint-shall-return-resolved-per-profile-gates]
- [ ] 1.2 Wrap profile resolution in a try/except that returns HTTP 200 with `{"gates": [], "warning": "<one-line cause>"}` on failure rather than 5xx [REQ: registry-endpoint-shall-return-resolved-per-profile-gates]
- [ ] 1.3 Confirm `MobileProjectType.register_gates()` returns `xcode-build` as a `GateDefinition`; add the conversion if the existing class-based gate is not yet wired into the registry interface [REQ: registry-endpoint-shall-return-resolved-per-profile-gates]
- [ ] 1.4 Join `profile.gate_retry_policy()` into each entry's `retry_policy` field; default missing entries to `"always"` [REQ: registry-entries-shall-declare-retry-policy-per-gate]
- [ ] 1.5 Add DEBUG log on successful endpoint calls naming project, profile class, and gate count; WARNING log with `exc_info=True` on profile load failure [REQ: registry-assembly-shall-be-observable]
- [ ] 1.6 Add `tests/unit/test_gates_registry_api.py` with cases for: web profile returns 13+ gates, mobile profile includes `xcode-build`, profile-load failure returns 200 + warning, retry-policy field defaults [REQ: registry-endpoint-shall-return-resolved-per-profile-gates]

## 2. Backend — surface failure reason in journal/changes API

- [ ] 2.1 Identify the existing journal/changes API handler(s) emitting per-gate entries (`/api/{project}/changes/{name}/journal` and `/api/{project}/changes` per-row gate fields). Locate the per-gate serialization site [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api]
- [ ] 2.2 Read `GateResult.terminal_reason` from state per gate run and add it as an optional `terminal_reason` field on the per-gate entry; omit the field when absent [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api]
- [ ] 2.3 Resolve the per-gate session JSONL path and call `gate_verdict.read_verdict_sidecar(session_path)` to fetch the sidecar; include `verdict_source` and `verdict_summary` on the per-gate entry when present [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api]
- [ ] 2.4 Wrap sidecar reads in try/except; on read/parse failure log WARNING with the sidecar path and continue, omitting the verdict fields from the response [REQ: sidecar-lookup-failures-shall-not-break-responses]
- [ ] 2.5 Add `tests/unit/test_journal_failure_reason.py` covering: terminal_reason surfaces for failed gates, verdict_source/summary surfaces from sidecar, pre-fix data omits new fields cleanly, corrupt sidecar logs warning and omits fields [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api]

## 3. Frontend — types + API client

- [ ] 3.1 In `web/src/lib/api.ts`, add `GateRegistryEntry` interface with `name`, `label`, `phase`, `position`, `run_on_integration`, `retry_policy`, `change_type_defaults` fields [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 3.2 Add `getGateRegistry(project): Promise<{gates: GateRegistryEntry[], warning?: string}>` typed wrapper over the new endpoint [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 3.3 Add `GatePayload` interface (`{result?, output?, ms?, terminal_reason?, verdict_source?, verdict_summary?}`) and extend `ChangeInfo` with `gates?: Record<string, GatePayload>`. Preserve all existing typed per-gate fields [REQ: per-change-gate-data-shall-be-available-as-a-generic-map]
- [ ] 3.4 In `web/src/lib/dag/types.ts`, widen `GateKind` from a literal union to `string` (preserve `impl` and `terminal` as documented well-known values in a JSDoc comment) [REQ: gatekind-type-shall-accept-any-registered-gate-name]

## 4. Frontend — registry context + shared rendering primitive

- [ ] 4.1 Add `web/src/contexts/GateRegistryContext.tsx` providing a React context with the project's gate registry, a loading state, and a fetch effect tied to the project name. Cache in-memory; refetch on project switch [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 4.2 Add `useGateRegistry()` hook returning `{registry, loading, error}`. On endpoint absence (404 or fetch error), return `{registry: null, loading: false, error: null}` so consumers fall back gracefully [REQ: frontend-shall-fall-back-when-registry-endpoint-is-unavailable]
- [ ] 4.3 Add a helper `resolveGateLabel(name, registry)` that returns the registry-provided label, or a title-cased name (`design-fidelity` → `"Design Fidelity"`, `i18n_check` → `"I18n Check"`) when the registry entry is absent [REQ: frontend-shall-fall-back-when-registry-endpoint-is-unavailable]
- [ ] 4.4 Mount `GateRegistryProvider` at the project-scoped root in `Dashboard.tsx` so all gate-rendering surfaces consume the same context [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]

## 5. Frontend — refactor LogPanel sub-tabs (highest-impact site)

- [ ] 5.1 In `web/src/components/LogPanel.tsx`, drop the `SubTab` literal union; replace with `string` (with `'task'` and `'merge'` as constants for the special tabs) [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 5.2 Rewrite `buildGateTabs(change, journal)` to enumerate `Object.keys(change.gates ?? {})` joined with the registry's gates (in registry order). Drop the hardcoded 5-entry array [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 5.3 For each enumerated gate, prefer `change.gates?.[name]` for result/output/ms, fall back to the legacy typed fields (`change.build_result`, etc.) when the map key is absent [REQ: per-change-gate-data-shall-be-available-as-a-generic-map]
- [ ] 5.4 Pass the resolved `label` from the registry helper into the GateOutputPane header instead of the hardcoded `gateLabels` lookup [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 5.5 Add a Playwright test `web/tests/e2e/log-panel-gate-tabs.spec.ts` that loads a fixture project exercising `design-fidelity` and `required-components` and asserts both sub-tabs appear in the LOG tab [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]

## 6. Frontend — refactor ChangeTable, GateBar, GateDetail, PhaseView

- [ ] 6.1 In `web/src/components/GateBar.tsx`, drop the hardcoded `gateLabels` map and the 6-entry `gates` array. Accept `registry` and `gates` (the per-change `Record<string, GatePayload>`) as props; iterate to render badges in registry order [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 6.2 Use `resolveGateLabel(name, registry)` and `g.name.charAt(0).toUpperCase()` only as a final fallback; prefer 1-2 letter abbreviations from the registry's `label` field [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 6.3 In `web/src/components/ChangeTable.tsx`, replace the 6-prop `<GateBar>` mounting and the `hasGates` typed-field check with a registry-driven `gates` map check (`Object.keys(c.gates ?? {}).length > 0` joined with legacy field presence) [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 6.4 In `web/src/components/GateDetail.tsx`, replace the hardcoded 6-entry `gates: GateSection[]` with `Object.entries(change.gates ?? {})` joined with legacy typed fields, in registry order [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 6.5 In `web/src/components/PhaseView.tsx`, update the `<GateBar>` mount to pass the registry + per-change `gates` map (no need for individual props) [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]

## 7. Frontend — DAG ingestion + retry reason

- [ ] 7.1 In `web/src/lib/dag/journalToAttemptGraph.ts`, drop the `GATE_KINDS` allow-list filtering; accept any non-empty string from the journal as a gate kind, rejecting only `''`, `'impl'`, and `'terminal'` (those are special) [REQ: gatekind-type-shall-accept-any-registered-gate-name]
- [ ] 7.2 In the same file, update `closeAttemptOnRetry` to follow the priority chain: failed-node-with-terminal_reason → `"<gate>: <terminal_reason>"`; any failed node → `"<gate>: gate-fail"`; failed merge → `"merge-conflict"`; else `"unknown"` + `console.warn` [REQ: retry-reason-shall-name-the-failing-gate-and-cause]
- [ ] 7.3 Extend `AttemptNode` to carry `terminalReason?: string` and `verdictSource?: string`; populate from the journal entry's per-gate `terminal_reason` and `verdict_source` fields (added in Section 2) [REQ: retry-reason-shall-name-the-failing-gate-and-cause]
- [ ] 7.4 In `web/src/lib/dag/enrichWithSessions.ts`, drop the literal `labelToGateKind` mapping; instead resolve any session label to a gate kind by lookup against the registry response (held in context) [REQ: gatekind-type-shall-accept-any-registered-gate-name]
- [ ] 7.5 Update the DAG retry-edge tooltip in `web/src/lib/dag/layout.ts` (or wherever the edge label is rendered) to surface the new retry-reason string verbatim instead of mapping to a fixed enum bucket [REQ: retry-reason-shall-name-the-failing-gate-and-cause]
- [ ] 7.6 Update `web/src/components/ChangeTimelineDetail.tsx` retry-reason cell to show the new string [REQ: retry-reason-shall-name-the-failing-gate-and-cause]

## 8. Tests

- [ ] 8.1 Extend `web/tests/unit/journalToAttemptGraph.test.ts` with cases asserting: a journal entry naming `design-fidelity` produces a node, a journal entry naming `xcode-build` produces a node, retry-reason composition uses `terminal_reason` when present, retry-reason composition uses `"<gate>: gate-fail"` when only result is present, the `"unknown"` fallback fires only when neither is present (and emits console.warn) [REQ: retry-reason-shall-name-the-failing-gate-and-cause]
- [ ] 8.2 Add `web/tests/e2e/registry-driven-gates.spec.ts` that asserts: against a fixture project exercising newer gates, all profile-registered gates appear in ChangeTable badges, LogPanel sub-tabs, and GateDetail [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 8.3 Add a unit test asserting that mounting the dashboard against a backend that returns 404 for the registry endpoint still renders gates present on `change.gates` with title-cased labels and shows no error banner [REQ: frontend-shall-fall-back-when-registry-endpoint-is-unavailable]

## 9. Verification + cleanup

- [ ] 9.1 Run `pnpm test:e2e` (web/) against a fixture project that exercised `design-fidelity` and `required-components`; confirm new and existing tests pass [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]
- [ ] 9.2 Run the full set-core unit + integration test suite; confirm no regression in journal API, learnings, or sentinel UI consumers [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api]
- [ ] 9.3 Manually verify on a project with retried attempts: DAG retry edges show `"<gate>: <reason>"` for known failures, `"unknown"` only for genuinely opaque attempts (and a `console.warn` is emitted in those cases) [REQ: retry-reason-shall-name-the-failing-gate-and-cause]
- [ ] 9.4 Audit the codebase for any remaining hardcoded gate-name lists or literal-union references in `web/src/`; document any intentional exclusions in a follow-up note [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry]

## Acceptance Criteria (from spec scenarios)

### Capability: gate-registry-api

- [ ] AC-1: WHEN `GET /api/{project}/gates/registry` is called for a project whose active profile is `WebProjectType` THEN the response includes all 8 universal gates AND all 5 web gates with `change_type_defaults` populated [REQ: registry-endpoint-shall-return-resolved-per-profile-gates, scenario: web-project-lists-all-13-gates]
- [ ] AC-2: WHEN the project's active profile is `MobileProjectType` THEN the response includes `xcode-build` alongside universal gates [REQ: registry-endpoint-shall-return-resolved-per-profile-gates, scenario: mobile-project-includes-xcode-build]
- [ ] AC-3: GIVEN a project whose profile cannot be resolved WHEN the registry endpoint is called THEN the response is HTTP 200 with `{"gates": [], "warning": "<cause>"}` and never 5xx [REQ: registry-endpoint-shall-return-resolved-per-profile-gates, scenario: profile-load-failure-returns-empty-warning]
- [ ] AC-4: GIVEN the web profile declares `gate_retry_policy()["e2e"] == "cached"` WHEN the registry returns the `e2e` entry THEN `retry_policy` equals `"cached"` [REQ: registry-entries-shall-declare-retry-policy-per-gate, scenario: cached-gate-has-explicit-policy]
- [ ] AC-5: GIVEN a gate absent from `gate_retry_policy()` WHEN the registry returns its entry THEN `retry_policy` equals `"always"` [REQ: registry-entries-shall-declare-retry-policy-per-gate, scenario: unspecified-gate-defaults-to-always]
- [ ] AC-6: WHEN the registry endpoint completes successfully THEN a DEBUG log includes project name, profile class name, and gate count [REQ: registry-assembly-shall-be-observable, scenario: successful-call-logs-debug]
- [ ] AC-7: GIVEN profile resolution raises an exception WHEN the registry endpoint handles the failure THEN a WARNING log includes the exception traceback [REQ: registry-assembly-shall-be-observable, scenario: profile-failure-logs-warning-with-traceback]

### Capability: web-dashboard-gate-rendering

- [ ] AC-8: GIVEN a profile registers a gate not present in any prior frontend code AND a change has produced a result for it WHEN the user opens the dashboard THEN the gate appears as a ChangeTable badge, LogPanel sub-tab, GateDetail entry, and DAG node — with no frontend code edit required [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry, scenario: newer-profile-registered-gate-appears-across-all-surfaces]
- [ ] AC-9: GIVEN the active profile is `WebProjectType` AND a change has executed `i18n_check`, `lint`, `design-fidelity`, `required-components` WHEN the user opens the LOG tab for that change THEN sub-tabs for all four appear alongside the universal-gate sub-tabs [REQ: gate-rendering-surfaces-shall-consume-the-gate-registry, scenario: all-web-profile-gates-render-in-the-log-tab]
- [ ] AC-10: GIVEN an attempt whose `design-fidelity` gate failed with `terminal_reason="max_turns"` WHEN the DAG retry-edge tooltip displays THEN the tooltip shows `"design-fidelity: max_turns"` AND the linear-view retry cell shows the same string [REQ: retry-reason-shall-name-the-failing-gate-and-cause, scenario: design-fidelity-max_turns-retry-shows-specific-reason]
- [ ] AC-11: GIVEN an attempt whose `lint` gate failed without a `terminal_reason` WHEN the retry-reason is derived THEN the result is `"lint: gate-fail"` and never `"unknown"` [REQ: retry-reason-shall-name-the-failing-gate-and-cause, scenario: generic-gate-failure-without-terminal_reason]
- [ ] AC-12: GIVEN an attempt whose journal contains no failed gate node and no merge failure WHEN the retry-reason is derived THEN the result is `"unknown"` AND a `console.warn` names the attempt [REQ: retry-reason-shall-name-the-failing-gate-and-cause, scenario: genuinely-unrecognizable-retry-falls-back]
- [ ] AC-13: GIVEN a backend that does not implement the registry endpoint WHEN the dashboard loads THEN gates present on `change.gates` still render with title-cased labels AND no error banner is shown for the missing endpoint [REQ: frontend-shall-fall-back-when-registry-endpoint-is-unavailable, scenario: older-backend-without-registry-endpoint]
- [ ] AC-14: GIVEN a journal entry references a gate named `"some-future-gate"` not in any prior frontend code WHEN `journalToAttemptGraph` ingests the entry THEN a DAG node is produced AND the node renders with the registry's label or a title-cased fallback [REQ: gatekind-type-shall-accept-any-registered-gate-name, scenario: unknown-gate-kind-from-journal-renders-as-dag-node]
- [ ] AC-15: GIVEN a `ChangeInfo` whose `gates["design-fidelity"]` carries `{result: "fail", terminal_reason: "max_turns"}` WHEN GateDetail renders THEN it displays result `"fail"` and terminal reason `"max_turns"` for the gate [REQ: per-change-gate-data-shall-be-available-as-a-generic-map, scenario: new-gate-read-through-generic-map]
- [ ] AC-16: GIVEN a `ChangeInfo` with `build_result: "pass"` but no `gates["build"]` entry WHEN ChangeTable renders the row badges THEN the build badge renders with status `"pass"` from the typed field [REQ: per-change-gate-data-shall-be-available-as-a-generic-map, scenario: legacy-typed-field-still-readable]

### Capability: gate-observability

- [ ] AC-17: GIVEN the `spec_verify` gate failed with `terminal_reason="timeout"` in state WHEN the journal/changes API is queried THEN the per-gate entry includes `"terminal_reason": "timeout"` [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api, scenario: verifier-gate-timeout-surfaces-terminal_reason]
- [ ] AC-18: GIVEN the `review` gate produced a verdict sidecar with `source="classifier_confirmed"` and `summary="0 critical findings"` WHEN the journal/changes API is queried THEN the per-gate entry includes `"verdict_source": "classifier_confirmed"` and `"verdict_summary": "0 critical findings"` [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api, scenario: review-gate-verdict-source-surfaces-from-sidecar]
- [ ] AC-19: GIVEN a change run before the verdict-sidecar feature shipped WHEN the journal/changes API is queried THEN the per-gate entry omits `terminal_reason`, `verdict_source`, `verdict_summary` AND contains no placeholder values like `"unknown"` or `null` for those fields [REQ: per-gate-failure-reason-shall-be-surfaced-in-journal-changes-api, scenario: pre-fix-data-omits-the-new-fields]
- [ ] AC-20: GIVEN a change whose `review.verdict.json` sidecar contains malformed JSON WHEN the journal/changes API is queried THEN the response succeeds with `result` populated and verdict fields omitted AND a WARNING log names the corrupt sidecar path [REQ: sidecar-lookup-failures-shall-not-break-responses, scenario: corrupt-sidecar-logged-but-ignored]
