## 1. Triage Template Generation

- [x] 1.1 Add `generate_triage_md()` function in `lib/orchestration/digest.sh` — takes ambiguities JSON, outputs markdown template with header instructions and per-AMB sections (`### AMB-NNN [type]`, source, description, `**Decision:**`, `**Note:**`)
- [x] 1.2 Add triage preservation logic — when `triage.md` already exists, parse existing decisions/notes and carry them over for ambiguities that still exist, mark removed ones with `[REMOVED]`, append new ones
- [x] 1.3 Call `generate_triage_md()` in `write_digest_output()` after writing `ambiguities.json` (only when ambiguity count > 0)
- [x] 1.4 Add tests for triage template generation: fresh generation, re-digest preservation, removed marking, new appending

## 2. Triage Parsing

- [x] 2.1 Add `parse_triage_md()` function in `lib/orchestration/digest.sh` — reads `triage.md`, extracts per-AMB decisions and notes, returns JSON array. Validates decisions against allowed set (`fix`/`defer`/`ignore`), treats invalid/blank as untriaged. Skips `[REMOVED]` entries.
- [x] 2.2 Add tests for triage parsing: valid decisions, invalid decisions treated as untriaged, note extraction, removed items skipped

## 3. Soft Gate in Planner

- [x] 3.1 Add `check_triage_gate()` function in `lib/orchestration/planner.sh` — called after auto-digest block in `cmd_plan()`. Returns: `no_ambiguities`, `needs_triage`, `has_untriaged`, `has_fixes`, `passed`
- [x] 3.2 Implement gate logic in `cmd_plan()`: on `needs_triage` → generate triage.md + exit 0 with message; on `has_untriaged` → print count + exit 0; on `has_fixes` → print fix count + exit 0; on `passed` → merge decisions into ambiguities.json + continue
- [x] 3.3 Add automated mode detection — when called from `cmd_start()` / orchestrator context, auto-defer all untriaged items instead of pausing. Set `resolved_by: "auto"`.
- [x] 3.4 Add tests for gate: no ambiguities pass-through, first-run generates triage, untriaged blocks, fixes block, all-triaged passes, automated mode auto-defers

## 4. Resolution Tracking

- [x] 4.1 Add `merge_triage_to_ambiguities()` function — reads parsed triage decisions, updates `ambiguities.json` with `resolution`, `resolution_note`, `resolved_by` fields per entry
- [x] 4.2 Add `merge_planner_resolutions()` function — after plan generation, reads `resolved_ambiguities` from plan changes, updates matching entries in `ambiguities.json` with `resolution: "planner-resolved"` and `resolved_by: "planner"`
- [x] 4.3 Add tests for resolution merging: triage merge, planner merge, auto-defer merge

## 5. Planner Prompt Modification

- [x] 5.1 Modify ambiguity section in planner prompt construction (planner.sh ~line 666-676) — filter to only `defer`-ed ambiguities, change instruction text to require explicit resolution per item
- [x] 5.2 Exclude `fixed`/`ignored` ambiguities from planner prompt
- [x] 5.3 Add `resolved_ambiguities` as optional field in plan output JSON schema validation
- [x] 5.4 Add tests for planner prompt: only defer items included, fixed/ignored excluded, resolved_ambiguities parsed from plan output

## 6. HTML Report Enhancement

- [x] 6.1 Replace flat `<ul>` ambiguity rendering in `reporter.sh` (~line 124-133) with HTML table: ID, Type, Description, Resolution, Note, Resolved By columns
- [x] 6.2 Add color-coding: green rows for `fixed`, blue for `deferred`/`planner-resolved`, gray for `ignored`, red for unresolved
- [x] 6.3 Add tests for report rendering: table structure, color-coding, zero ambiguities omission
