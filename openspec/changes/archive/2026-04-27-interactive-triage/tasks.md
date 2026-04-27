# Tasks: interactive-triage

## 1. Backend — Per-item triage write function

- [ ] 1.1 Add `submit_triage_decision(digest_dir, amb_id, decision, note)` to `lib/set_orch/digest.py` — reads triage.md, checks immutability (reject if decision already exists for amb_id), writes decision+note into the `**Decision:**`/`**Note:**` fields for the matching AMB section, then calls `merge_triage_to_ambiguities()` for that single item [REQ: triage-decision-persistence]
- [ ] 1.2 Add `get_triage_items(digest_dir)` to `lib/set_orch/digest.py` — reads ambiguities.json + triage.md, returns list of dicts with id/type/description/source/affects/decision/note/locked fields, plus stats dict (total/triaged/pending) [REQ: triage-api-endpoints]

## 2. Backend — API endpoints

- [ ] 2.1 Add `GET /api/{project}/triage` endpoint in `lib/set_orch/api/orchestration.py` — calls `get_triage_items()`, returns `{ items: [...], stats: {total, triaged, pending} }` [REQ: triage-api-endpoints]
- [ ] 2.2 Add `POST /api/{project}/triage/{amb_id}` endpoint in `lib/set_orch/api/orchestration.py` — validates decision is fix/defer/ignore, calls `submit_triage_decision()`, returns 200/400/404/409 appropriately [REQ: triage-api-endpoints]

## 3. Backend — Sentinel triage wait mode

- [ ] 3.1 Add `triage_mode` field support to orchestration config loading (read from `orchestration.yaml`, default `auto`) [REQ: sentinel-triage-wait-mode]
- [ ] 3.2 Modify triage gate integration in `lib/set_orch/planner.py:cmd_plan()` (lines 1695-1708) — when `triage_mode == "interactive"`, return a blocking status instead of raising RuntimeError; when `auto`, preserve existing auto-defer behavior [REQ: sentinel-triage-wait-mode]
- [ ] 3.3 Integrate triage wait into sentinel loop — when triage gate returns blocking status, log "Waiting for triage decisions (N items pending)" and skip to next iteration without proceeding to planner [REQ: sentinel-triage-wait-mode]

## 4. Frontend — Triage form component

- [ ] 4.1 Create `web/src/components/TriageForm.tsx` — fetches `GET /api/{project}/triage`, renders a card per item with: type badge, description, source, affects list, three action buttons (fix/defer/ignore), optional note textarea, submit button per card [REQ: web-ui-triage-form]
- [ ] 4.2 Implement per-card submit — on click action button + submit: POST to `/api/{project}/triage/{amb_id}`, on 200 transition card to locked state (show decision + lock icon, disable buttons/textarea), on 409 show already-decided message [REQ: web-ui-triage-form]
- [ ] 4.3 Implement progress indicator — show "Triaged: N/M" bar below cards, update after each successful submit; when all triaged show "All triaged — planner will proceed on next sentinel iteration" [REQ: web-ui-triage-form]
- [ ] 4.4 Replace `<MarkdownPanel>` with `<TriageForm>` in `web/src/components/DigestView.tsx` (line 146) — use TriageForm when untriaged items exist, fall back to MarkdownPanel when all are locked (or no items) [REQ: web-ui-triage-form]

## 5. Prompt-based triage

- [ ] 5.1 Add prompt triage function to sentinel skill — when triage gate returns `has_untriaged` in interactive mode and running in a prompt session, iterate untriaged items: present each via AskUserQuestion with options ["fix — spec needs correction", "defer — planner will decide", "ignore — out of scope"], persist response via `submit_triage_decision()` [REQ: prompt-based-triage]
- [ ] 5.2 Implement sequential prompting loop — after each AskUserQuestion response, check remaining untriaged count; if > 0 present next item, if 0 log "All triaged" and let gate pass [REQ: prompt-based-triage]
- [ ] 5.3 Handle "Other" free-text response from AskUserQuestion — parse as note, default decision to "defer" unless response text contains "fix" or "ignore" explicitly [REQ: prompt-based-triage]

## 6. Tests

- [ ] 6.1 Unit test `submit_triage_decision()` — test successful write, immutability rejection (409 case), unknown amb_id (404 case), invalid decision (400 case) [REQ: triage-decision-persistence]
- [ ] 6.2 Unit test `get_triage_items()` — test with mixed decided/undecided items, empty ambiguities, correct stats calculation [REQ: triage-api-endpoints]
- [ ] 6.3 Integration test for API endpoints — test GET/POST round-trip: submit a decision, verify GET reflects it as locked, verify re-submit returns 409 [REQ: triage-api-endpoints]
- [ ] 6.4 Integration test for sentinel triage wait — test that `triage_mode: interactive` blocks planning when untriaged items exist, and passes when all triaged [REQ: sentinel-triage-wait-mode]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN GET /api/{project}/triage is called and ambiguities exist THEN response contains items array with structured fields and stats [REQ: triage-api-endpoints, scenario: get-triage-returns-structured-items]
- [ ] AC-2: WHEN POST decision is called on item with no prior decision THEN decision is persisted and item is locked [REQ: triage-api-endpoints, scenario: post-decision-succeeds]
- [ ] AC-3: WHEN POST is called on already-decided item THEN 409 returned and existing decision unchanged [REQ: triage-api-endpoints, scenario: post-decision-rejected-for-already-decided-item]
- [ ] AC-4: WHEN triage card submit clicked THEN POST sent, card transitions to locked state with lock icon [REQ: web-ui-triage-form, scenario: decision-submitted-from-card]
- [ ] AC-5: WHEN last untriaged item receives a decision THEN progress shows "All triaged" [REQ: web-ui-triage-form, scenario: all-items-triaged]
- [ ] AC-6: WHEN sentinel in interactive mode and untriaged items exist THEN logs waiting message and does not proceed to planning [REQ: sentinel-triage-wait-mode, scenario: interactive-mode-blocks-until-triaged]
- [ ] AC-7: WHEN triage_mode is auto THEN auto-defers all and proceeds immediately [REQ: sentinel-triage-wait-mode, scenario: auto-mode-preserves-existing-behavior]
- [ ] AC-8: WHEN user resolves items via mixed surfaces (web + prompt) THEN both write to same triage.md and gate passes after last item [REQ: triage-re-check-loop, scenario: partial-triage-via-web-then-prompt]
