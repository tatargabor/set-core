## IN SCOPE
- Dynamic rendering of all gates returned by the gate-registry HTTP endpoint in the Changes tab badges, LOG tab sub-tabs, GateDetail expanded panel, DAG nodes, and PhaseView mounts.
- Per-gate result, output, timing, and failure-reason display sourced from the journal/changes API response without hardcoded gate name lists.
- Retry-reason display naming the failing gate and its `terminal_reason`/verdict source whenever the backend has emitted them.
- Graceful fallback rendering when the gate-registry endpoint is unavailable — keys present on the per-change `gates` map render with default labels.

## OUT OF SCOPE
- Visual redesign of GateBar, GateNode, or GateDetail — only the data binding changes.
- Adding new gate-execution behavior or pipeline modifications.
- Mobile-specific UI affordances beyond `xcode-build` appearing through the dynamic registry.
- Persisting gate-registry data to local storage; in-memory React context cache is sufficient.

## ADDED Requirements

### Requirement: Gate-rendering surfaces shall consume the gate registry
The web dashboard SHALL fetch the gate registry for the active project on load and use it to drive rendering in: ChangeTable row badges, LogPanel sub-tabs, GateDetail panel, DAG attempt nodes, and PhaseView change rows. No gate-rendering surface SHALL hardcode a literal gate-name list.

#### Scenario: Newer profile-registered gate appears across all surfaces
- **GIVEN** a profile registers a gate not present in any prior frontend code (e.g., `accessibility`)
- **AND** a change has run and produced a result for that gate
- **WHEN** the user opens the dashboard
- **THEN** the gate SHALL appear as a badge in the ChangeTable row, as a sub-tab in the LOG tab, as an entry in GateDetail, and as a node in the DAG
- **AND** no frontend code edit SHALL be required to enable this

#### Scenario: All web profile gates render in the LOG tab
- **GIVEN** the active profile is `WebProjectType`
- **AND** a change has executed `i18n_check`, `lint`, `design-fidelity`, and `required-components` among other gates
- **WHEN** the user clicks the change row and opens the LOG tab
- **THEN** sub-tabs for `i18n_check`, `lint`, `design-fidelity`, and `required-components` SHALL appear alongside the universal-gate sub-tabs

### Requirement: Retry reason shall name the failing gate and cause
When an attempt is closed via retry, the GUI SHALL derive the retry-reason string from the failing gate's name and its `terminal_reason` or verdict source, in this priority order: (1) failed node with `terminal_reason` → `"<gate>: <terminal_reason>"`, (2) any failed node → `"<gate>: gate-fail"`, (3) failed `merge` node → `"merge-conflict"`, (4) no recognizable failure → `"unknown"` (logged as `console.warn`).

#### Scenario: Design-fidelity max_turns retry shows specific reason
- **GIVEN** an attempt whose `design-fidelity` gate failed with `terminal_reason="max_turns"`
- **WHEN** the DAG retry-edge tooltip is displayed for that attempt
- **THEN** the tooltip SHALL show `"design-fidelity: max_turns"`
- **AND** the linear-view retry cell SHALL show the same string

#### Scenario: Generic gate failure without terminal_reason
- **GIVEN** an attempt whose `lint` gate failed but no `terminal_reason` was emitted
- **WHEN** the retry-reason is derived
- **THEN** the result SHALL be `"lint: gate-fail"` — never bare `"unknown"`

#### Scenario: Genuinely unrecognizable retry falls back
- **GIVEN** an attempt whose journal contains no failed gate node and no merge failure
- **WHEN** the retry-reason is derived
- **THEN** the result SHALL be `"unknown"`
- **AND** a `console.warn` SHALL be emitted naming the attempt for diagnosis

### Requirement: Frontend shall fall back when registry endpoint is unavailable
When the gate-registry endpoint returns 404 (older backend) or fails to load, the GUI SHALL render whatever gate keys appear on the per-change `gates` map with title-cased labels derived from the gate name (`design-fidelity` → `"Design Fidelity"`). The dashboard SHALL NOT show an error banner solely because the registry endpoint is missing.

#### Scenario: Older backend without registry endpoint
- **GIVEN** a backend that does not implement `/api/{project}/gates/registry`
- **WHEN** the dashboard loads
- **THEN** gates present on `change.gates` SHALL still render
- **AND** their labels SHALL be the title-cased gate name
- **AND** no error banner SHALL be shown for the missing endpoint

### Requirement: GateKind type shall accept any registered gate name
The `GateKind` type in `web/src/lib/dag/types.ts` SHALL be widened to `string` (or an equivalent open type) so any gate name returned by the backend journal or registry is honored. The `GATE_KINDS` allow-list filtering in `journalToAttemptGraph` SHALL be replaced with rejection of empty strings and reserved kinds (`impl`, `terminal`) only.

#### Scenario: Unknown gate kind from journal renders as DAG node
- **GIVEN** a journal entry references a gate named `"some-future-gate"` that is not in any prior frontend code
- **WHEN** `journalToAttemptGraph` ingests the entry
- **THEN** a DAG node SHALL be produced for the gate
- **AND** the node SHALL render with the registry's label or a title-cased fallback

### Requirement: Per-change gate data shall be available as a generic map
The `ChangeInfo` type in `web/src/lib/api.ts` SHALL include an optional `gates: Record<string, GatePayload>` field where `GatePayload = {result?, output?, ms?, terminal_reason?, verdict_source?, verdict_summary?}`. Existing typed per-gate fields (`build_result`, `gate_build_ms`, etc.) SHALL be preserved during the transition. Frontend code SHALL prefer `gates[name]` and fall back to typed fields only when the map key is absent.

#### Scenario: New gate read through generic map
- **GIVEN** a `ChangeInfo` whose `gates["design-fidelity"]` carries `{result: "fail", terminal_reason: "max_turns"}`
- **WHEN** GateDetail renders
- **THEN** it SHALL display result `"fail"` and the terminal reason `"max_turns"` for the `design-fidelity` gate

#### Scenario: Legacy typed field still readable
- **GIVEN** a `ChangeInfo` with `build_result: "pass"` but no `gates["build"]` entry
- **WHEN** ChangeTable renders the row badges
- **THEN** the build badge SHALL render with status `"pass"` from the typed field
