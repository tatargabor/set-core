# Proposal: interactive-triage

## Why

The triage gate currently has two modes: (1) interactive CLI mode that prints "edit triage.md then re-run" and exits, requiring manual file editing, and (2) automated mode that auto-defers everything to the planner. Neither provides real human-in-the-loop decision-making. In automated E2E runs this is fine, but for production orchestration the user has no practical way to resolve ambiguities — the web dashboard shows triage.md read-only, and no prompt-based interaction exists. Contradictory requirements and missing references deserve human judgment, not LLM guessing.

## What Changes

- **Triage API endpoints** — new `GET /api/{project}/triage` (structured JSON with per-item status) and `POST /api/{project}/triage/{amb_id}` (submit a single immutable decision)
- **Web UI triage form** — replace the read-only markdown panel with interactive cards: three action buttons (fix/defer/ignore) + optional textarea note per ambiguity, locked after submission
- **Prompt-based triage** — integrate AskUserQuestion into the sentinel flow for interactive sessions: present each untriaged ambiguity with fix/defer/ignore options
- **Sentinel triage wait** — when `triage_mode: interactive` in orchestration config, the sentinel loop blocks at the triage gate until all items are resolved (re-checks each iteration)
- **Re-check loop** — after each decision submission, re-evaluate remaining untriaged count; when zero remain, gate passes and planner proceeds
- **Immutable decisions** — once submitted, a decision is locked (409 Conflict on re-submit); no edit/undo

## Capabilities

### New Capabilities
- `interactive-triage` — the interactive triage resolution system (web form, prompt flow, API, sentinel wait)

### Modified Capabilities
_(none — existing triage pipeline stays intact, new interaction surfaces are additive)_

## Impact

- `lib/set_orch/api/orchestration.py` — new triage endpoints
- `lib/set_orch/planner.py` — sentinel wait mode in triage gate
- `lib/set_orch/digest.py` — per-item write-back to triage.md + ambiguities.json
- `web/src/components/DigestView.tsx` — new TriageForm component replacing MarkdownPanel
- `orchestration.yaml` schema — new `triage_mode` field (auto/interactive)
- Sentinel skill — AskUserQuestion integration for prompt-based triage
