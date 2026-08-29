## 1. Layer 1 — stage derivation module

- [x] 1.1 Create `lib/set_orch/fleet/stage.py`: resolve flow + position from a project's `openspec/changes/` tree per the design mapping (archive → design → apply → verify → proposal; artifact-less directory = no position), reusing `read_progress` for task counts; logging carries shapes/counts only, never stage values or project identifiers [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent]
- [x] 1.2 Session→change join: work-cycle record first (`read_purposes`), session-record inference second; no single-active-change guessing; explicit gap when neither resolves [REQ: the-stage-is-joined-to-the-agent-through-its-session]
- [x] 1.3 Declared override: read `stageOrder` for the stage field from the project's project-status answer (existing validation, all-or-nothing); declared flow replaces derived per project; malformed declaration falls back to derived [REQ: a-producer-declared-flow-replaces-the-derived-flow]
- [x] 1.4 Gap semantics: every unresolvable case yields an explicit gap value, distinguishable from a resolved position and from nothing-started; no fabricated stages [REQ: a-gap-is-reported-never-filled]
- [x] 1.5 Unit tests for the derivation mapping table (each row of the design's mapping, plus artifact-less dir and no-tree project), written against the mapping table before the resolver is wired anywhere [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent]
- [x] 1.6 Unit tests: two agents on two changes resolve independently; join survives a pid change with the same session id [REQ: the-stage-is-joined-to-the-agent-through-its-session]
- [x] 1.7 Unit tests: declared flow replaces derived; stray value kept with outside marker; malformed declaration (non-list, empty, blank member, duplicate) → derived fallback, never a partial declared flow [REQ: a-producer-declared-flow-replaces-the-derived-flow]
- [x] 1.8 Unit tests: gap shape in every unresolvable case; assert the gap value is NOT equal to any stage position and NOT equal to the nothing-started value [REQ: a-gap-is-reported-never-filled]

## 2. Layer 1 — payload exposure

- [x] 2.1 Add the resolved stage to `_agent_payload` in `lib/set_orch/api/fleet.py` as an additive field; agents without a resolution keep every existing field byte-identical [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field]
- [x] 2.2 Verify no derived value is persisted: run the payload path over a fixture project and assert no file under the runtime/state dirs changed (sha256 before/after) [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field]
- [x] 2.3 Regression test on the payload route: existing payload tests pass unchanged with the field present; absent-resolution agents omit only the resolved shape [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field]

## 3. Web — tree and strip

- [x] 3.1 Extend `web/src/lib/fleetTypes.ts` with the stage field's type (flow, position, gap variants) matching the payload tests [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field]
- [x] 3.2 Sub-rows under each project row, honouring query/live-mode filtering and zero-live-agent suppression — implemented as DOM children of `ProjectRow` rather than in `buildColumnView` (deviation recorded 2026-08-29): a sub-row that is a child of its row is hidden by every filter that hides the row, by construction, instead of by a second filter copy kept in step [REQ: each-project-row-can-expand-to-indented-agent-sub-rows]
- [x] 3.3 Render indented, visually subordinate sub-rows in `FleetProjectColumn` (selected project expanded by default) [REQ: each-project-row-can-expand-to-indented-agent-sub-rows]
- [x] 3.4 Wire sub-row click to `writeView(project, {enlarged: pid})` so selection and per-project restore behave exactly like tile selection [REQ: clicking-an-agent-sub-row-selects-that-agent]
- [x] 3.5 Build the compact stage-strip sub-row component consuming the payload's flow + position: completed/current/pending styles from unclaimed hues, empty state, gap state, amber/⚑ strays; legible at sub-row height with no hover dependency [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip]
- [x] 3.6 Web unit tests: filtering hides sub-rows with the project row; no orphaned sub-rows; click focuses the agent and survives leave/return [REQ: clicking-an-agent-sub-row-selects-that-agent]
- [x] 3.7 Web unit tests for the strip: mid-flow agent renders done/running/pending per position; nothing-started, gap, and stray each render their distinct state; a non-OpenSpec declared flow renders its own stage names in declared order [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip]
- [x] 3.8 Stash-and-rerun the new Python and web tests: each fails on its assertion against reverted code and passes restored; name the two `.pyc`/restore traps in the run notes if hit [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent]

## 4. Verification

- [x] 4.1 Full Python and web suites: set-diff against a pre-change baseline (regression-baseline recipe), no new failures [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field]
- [ ] 4.2 Visual check, in the browser, against the running dashboard: tree reads as a subtree, strips read at a glance mid-flow, gap and empty states are distinct from each other, and no colour collides with the fleet's existing status dots; record what is seen, not only that it was looked at [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip]
- [ ] 4.3 Look at a project with a declared flow and confirm the strip renders the producer's stages, plus one gapped agent on the same screen, confirming both in one look [REQ: a-producer-declared-flow-replaces-the-derived-flow]

## Acceptance Criteria (from spec scenarios)

### the-framework-derives-a-default-openspec-stage-for-every-agent

- [x] AC-1: WHEN the project has an active change whose tasks.md carries at least one unchecked task THEN the agent joined to that change resolves to flow [proposal, design, apply, verify, archive] at position apply [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent, scenario: a-change-with-unchecked-tasks-is-in-apply]
- [x] AC-2: WHEN the project's active change directory has no tasks.md yet THEN the agent resolves to position design [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent, scenario: a-change-without-a-tasks-md-is-in-design]
- [x] AC-3: WHEN the active change has a tasks.md whose tasks are all checked THEN the agent resolves to position verify [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent, scenario: a-change-with-every-task-checked-is-in-verify]
- [x] AC-4: WHEN the change the agent is joined to exists only under openspec/changes/archive/ THEN the agent resolves to position archive [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent, scenario: an-archived-change-is-done]
- [x] AC-5: WHEN the active change directory carries a proposal but no design artifact and no tasks.md THEN the agent resolves to position proposal [REQ: the-framework-derives-a-default-openspec-stage-for-every-agent, scenario: a-proposal-only-change-is-in-proposal]

### the-stage-is-joined-to-the-agent-through-its-session

- [x] AC-6: WHEN two live agents of one project are joined to two different active changes THEN each agent's payload carries the stage of its own change [REQ: the-stage-is-joined-to-the-agent-through-its-session, scenario: two-agents-on-different-changes-get-different-stages]
- [x] AC-7: WHEN an agent's process is replaced by a new pid but the session id is unchanged THEN the resolved stage follows the session [REQ: the-stage-is-joined-to-the-agent-through-its-session, scenario: the-join-is-keyed-on-session-identity-not-pid]

### a-producer-declared-flow-replaces-the-derived-flow

- [x] AC-8: WHEN a project declares stageOrder [triage, fixing, shipping] and an agent's answer carries stage fixing THEN the agent's flow is [triage, fixing, shipping] at position fixing and the OpenSpec flow is not used [REQ: a-producer-declared-flow-replaces-the-derived-flow, scenario: a-declared-flow-replaces-the-openspec-default]
- [x] AC-9: WHEN an agent's stage value does not appear in the project's declared order THEN the payload carries the value with an outside-the-flow marker and no declared stage is removed [REQ: a-producer-declared-flow-replaces-the-derived-flow, scenario: a-value-outside-the-declared-order-is-marked-not-dropped]
- [x] AC-10: WHEN the declared stage order is not a list, is empty, contains a blank or non-string member, or a duplicate THEN no declared flow is resolved and the default derivation applies [REQ: a-producer-declared-flow-replaces-the-derived-flow, scenario: a-malformed-declaration-yields-no-flow]

### a-gap-is-reported-never-filled

- [x] AC-11: WHEN an agent's session cannot be joined to any change and the project has no declared flow THEN the payload carries a stage whose state is a gap, distinguishable from any resolved position and from nothing started [REQ: a-gap-is-reported-never-filled, scenario: an-agent-with-no-resolvable-change-carries-an-explicit-gap]

### the-stage-reaches-the-fleet-agent-payload-as-an-additive-field

- [x] AC-12: WHEN the payload is served for a fleet where some agents have no resolvable stage THEN every agent entry carries all previously specified fields unchanged [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field, scenario: an-agent-with-no-resolved-stage-does-not-disturb-existing-fields]
- [x] AC-13: WHEN a stage is resolved from a consumer project's tree or declared answer THEN no value derived from that resolution is written to any file, cache, or log that outlives the request [REQ: the-stage-reaches-the-fleet-agent-payload-as-an-additive-field, scenario: nothing-derived-is-persisted]

### each-project-row-can-expand-to-indented-agent-sub-rows

- [x] AC-14: WHEN a project row is rendered for a project whose fleet payload carries live agents THEN one indented sub-row appears beneath it per agent and no agent appears under a project it does not belong to [REQ: each-project-row-can-expand-to-indented-agent-sub-rows, scenario: a-project-with-live-agents-shows-them-as-sub-rows]
- [x] AC-15: WHEN the column is filtered so a project row is hidden THEN that project's agent sub-rows are hidden with it and no orphaned sub-row remains [REQ: each-project-row-can-expand-to-indented-agent-sub-rows, scenario: project-level-filtering-still-applies-to-the-tree]

### clicking-an-agent-sub-row-selects-that-agent

- [x] AC-16: WHEN the user clicks the sub-row of an agent of the selected project THEN that agent becomes the focused agent exactly as if its tile had been clicked [REQ: clicking-an-agent-sub-row-selects-that-agent, scenario: a-sub-row-click-focuses-the-agent]
- [x] AC-17: WHEN the user focuses agent A of project P, selects another project, then returns to P THEN agent A is focused again [REQ: clicking-an-agent-sub-row-selects-that-agent, scenario: the-selection-survives-leaving-and-returning]

### each-agent-sub-row-renders-its-stage-as-a-compact-strip

- [x] AC-18: WHEN an agent is resolved at position apply of [proposal, design, apply, verify, archive] THEN proposal and design render completed, apply running, verify and archive pending [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip, scenario: mid-flow-agent-reads-at-a-glance]
- [x] AC-19: WHEN an agent carries a gap because nothing was ever started THEN the strip renders the empty state, visibly different from any resolved position and from a resolution-failure gap [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip, scenario: nothing-started-renders-the-empty-state]
- [x] AC-20: WHEN an agent's stage value does not appear in its flow THEN the strip shows the value marked as outside the flow alongside the full flow, dropping neither [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip, scenario: an-outside-the-flow-value-is-marked-on-the-strip]
- [x] AC-21: WHEN a project declares a flow whose stage names are not OpenSpec stages THEN the strip renders the producer's stage names in the declared order with the same mechanics [REQ: each-agent-sub-row-renders-its-stage-as-a-compact-strip, scenario: a-declared-flow-renders-in-the-producers-own-stages]
