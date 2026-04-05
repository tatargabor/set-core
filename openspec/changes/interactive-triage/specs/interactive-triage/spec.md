## ADDED Requirements

## IN SCOPE
- Per-item triage decision submission via REST API
- Web UI form with action buttons and note textarea per ambiguity
- Prompt-based triage via AskUserQuestion in interactive sentinel sessions
- Sentinel wait mode that blocks planning until triage is complete
- Immutable decisions (no edit after submit)
- Re-check loop: after each decision, re-evaluate remaining count
- `triage_mode` config field in orchestration.yaml (auto/interactive)

## OUT OF SCOPE
- Type-specific UI (confirm/reject for assumptions, pick A/B for contradictions) — fix/defer/ignore is universal
- Batch submit (decisions are per-item, immediate lock)
- Undo/edit of submitted decisions
- Webhook/push notifications to sentinel (uses next-loop polling)
- Priority sorting by ambiguity type (displayed in digest order)
- Collapsible groups or drag-and-drop reordering

### Requirement: Triage API endpoints
The system SHALL expose REST endpoints for structured triage interaction. `GET /api/{project}/triage` SHALL return all ambiguity items with their current decision status. `POST /api/{project}/triage/{amb_id}` SHALL accept a single decision and persist it.

#### Scenario: GET triage returns structured items
- **WHEN** `GET /api/{project}/triage` is called and ambiguities exist
- **THEN** the response contains `items` (array of ambiguity objects with id, type, description, source, affects, decision, note, locked fields) and `stats` (total, triaged, pending counts)

#### Scenario: GET triage with no ambiguities
- **WHEN** `GET /api/{project}/triage` is called and no ambiguities exist
- **THEN** the response contains empty `items` array and `stats` with all zeros

#### Scenario: POST decision succeeds
- **WHEN** `POST /api/{project}/triage/{amb_id}` is called with `{"decision": "defer", "note": "planner can handle this"}` and the item has no prior decision
- **THEN** the decision is persisted to triage.md and ambiguities.json, the response is `200 { ok: true }`, and the item is locked

#### Scenario: POST decision rejected for already-decided item
- **WHEN** `POST /api/{project}/triage/{amb_id}` is called and the item already has a decision
- **THEN** the response is `409 { error: "already_decided" }` and the existing decision is unchanged

#### Scenario: POST decision with invalid value
- **WHEN** `POST /api/{project}/triage/{amb_id}` is called with a decision value other than fix/defer/ignore
- **THEN** the response is `400 { error: "invalid_decision" }`

#### Scenario: POST decision with unknown amb_id
- **WHEN** `POST /api/{project}/triage/{amb_id}` is called with an ID not in ambiguities.json
- **THEN** the response is `404 { error: "not_found" }`

### Requirement: Triage decision persistence
The system SHALL write decisions to both triage.md and ambiguities.json atomically per item. Decisions SHALL be immutable once written.

#### Scenario: Decision written to triage.md
- **WHEN** a decision is submitted for AMB-003 with decision "ignore" and note "out of scope for v1"
- **THEN** the triage.md entry for AMB-003 has `**Decision:** ignore` and `**Note:** out of scope for v1`

#### Scenario: Decision merged to ambiguities.json
- **WHEN** a decision is submitted for AMB-003 with decision "ignore"
- **THEN** ambiguities.json entry for AMB-003 has `resolution: "ignored"`, `resolved_by: "triage"`, and `resolution_note` set to the note

#### Scenario: Immutability enforced at persistence layer
- **WHEN** triage.md already contains a non-blank Decision for an AMB item
- **THEN** any attempt to overwrite that decision SHALL be rejected before writing

### Requirement: Web UI triage form
The system SHALL provide an interactive triage form in the web dashboard's Digest view, replacing the read-only markdown panel when untriaged items exist.

#### Scenario: Triage card displayed for untriaged item
- **WHEN** the triage tab is opened and AMB-001 has no decision
- **THEN** a card is shown with: ambiguity type badge, description, source, affected requirements, three action buttons (fix/defer/ignore), and an optional note textarea

#### Scenario: Decision submitted from card
- **WHEN** the user clicks "defer" on AMB-001's card and optionally enters a note
- **THEN** a POST is sent to `/api/{project}/triage/AMB-001`, and on success the card transitions to locked state showing the decision with a lock icon

#### Scenario: Locked card is non-editable
- **WHEN** a card is in locked state (decision already submitted)
- **THEN** the action buttons and textarea are disabled/hidden, the decision and note are displayed as read-only text

#### Scenario: Progress indicator updates
- **WHEN** a decision is submitted
- **THEN** the progress indicator updates (e.g., "Triaged: 3/10") reflecting the new count from `stats`

#### Scenario: All items triaged
- **WHEN** the last untriaged item receives a decision
- **THEN** the progress indicator shows "All triaged" and a status message indicates the planner will proceed on the next sentinel iteration

### Requirement: Prompt-based triage
The system SHALL support triage via AskUserQuestion in interactive sentinel sessions, presenting each untriaged ambiguity sequentially with fix/defer/ignore options.

#### Scenario: Triage prompt shown for untriaged item
- **WHEN** the sentinel reaches the triage gate in interactive mode and untriaged items exist
- **THEN** the first untriaged item is presented via AskUserQuestion with options: "fix — spec needs correction", "defer — planner will decide", "ignore — out of scope"

#### Scenario: Decision from prompt persisted
- **WHEN** the user selects an option (e.g., "defer") from the AskUserQuestion prompt
- **THEN** the decision is persisted identically to a web UI submission (same triage.md + ambiguities.json write)

#### Scenario: Sequential prompting
- **WHEN** a prompt decision is submitted and more untriaged items remain
- **THEN** the next untriaged item is presented immediately via another AskUserQuestion

#### Scenario: All items resolved via prompt
- **WHEN** the last item is resolved via prompt
- **THEN** the triage gate returns `passed` and the sentinel proceeds to planning

### Requirement: Sentinel triage wait mode
The system SHALL support a `triage_mode` configuration that controls whether the sentinel auto-defers or waits for human triage decisions.

#### Scenario: Auto mode preserves existing behavior
- **WHEN** `triage_mode` is `auto` (or unset) in orchestration config
- **THEN** the triage gate auto-defers all ambiguities and proceeds to planning immediately (existing behavior)

#### Scenario: Interactive mode blocks until triaged
- **WHEN** `triage_mode` is `interactive` and untriaged items exist
- **THEN** the sentinel logs "Waiting for triage decisions (N items pending)" and does not proceed to planning

#### Scenario: Interactive mode re-checks each iteration
- **WHEN** the sentinel loop iterates and `triage_mode` is `interactive`
- **THEN** the triage gate re-evaluates the untriaged count from triage.md; if zero remain, gate passes

#### Scenario: Fix items block planning
- **WHEN** any triaged item has decision "fix" (regardless of mode)
- **THEN** the gate returns `has_fixes` and planning is blocked until the spec is corrected and re-digested

### Requirement: Triage re-check loop
The system SHALL re-evaluate triage completeness after each decision submission, enabling incremental resolution from either surface.

#### Scenario: Partial triage via web then prompt
- **WHEN** a user resolves 5/10 items via web UI, then resolves the remaining 5 via prompt
- **THEN** both surfaces read the same triage.md state, and the gate passes after the 10th decision regardless of which surface submitted it

#### Scenario: Gate transition from has_untriaged to passed
- **WHEN** the last untriaged item is resolved (from any surface)
- **THEN** the next triage gate check returns `passed` with the full count
