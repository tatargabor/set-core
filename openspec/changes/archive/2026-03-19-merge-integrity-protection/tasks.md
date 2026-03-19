# Tasks: Merge Integrity Protection

## 1. Test Fixture — Reproduce Merge Data Loss

- [x] 1.1 Create test script `tests/merge/test_merge_integrity.sh` that sets up a temp git repo with two branches modifying a schema file [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 1.2 Branch A (main): base schema with ~19 model definitions [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 1.3 Branch B (feature): base + 2 additional models (Session, PasswordResetToken) with overlapping edits to create a realistic conflict [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 1.4 Run `wt-merge --llm-resolve` and record baseline: merge succeeds even if models are lost (this is the bug we are fixing) [REQ: diff-based-conservation-check-after-llm-merge]

**NOTE:** Tasks 1.1–1.4 MUST be completed and baseline results recorded BEFORE any modifications in tasks 2–6.

## 2. Generic Conservation Check in wt-merge

- [x] 2.1 Modify `llm_resolve_conflicts()` to populate a bash array `LLM_RESOLVED_FILES` (or write to temp file) with the list of files it resolved [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 2.2 Add `compute_additions()` function: given merge-base, ours, theirs versions of a file, compute added lines as set of trimmed non-blank content lines [REQ: conservation-check-computes-additions-from-merge-base]
- [x] 2.3 Add `conservation_check()` function: compare ours_added and theirs_added against merged result, return missing lines [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 2.4 Handle edge cases in conservation_check: binary files (skip via `git diff --numstat` null check), file new on both sides (base = empty), delete/modify conflict (skip) [REQ: conservation-check-computes-additions-from-merge-base]
- [x] 2.5 Add `run_conservation_checks()` function: iterate over `LLM_RESOLVED_FILES`, run conservation_check on each, collect results [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 2.6 Integrate into merge flow: call `run_conservation_checks()` after `llm_resolve_conflicts()` succeeds and BEFORE `git commit --no-edit` [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 2.7 On failure: `git reset --merge` (merge is uncommitted at this point), log detailed report (file, side, lost lines), exit non-zero [REQ: conservation-check-logs-detailed-report]
- [x] 2.8 Add `--no-conservation-check` flag to wt-merge usage/parsing [REQ: diff-based-conservation-check-after-llm-merge]

## 3. File-Type Strategy Config

- [x] 3.1 Add `load_merge_strategies()` function: parse `merge_strategies` from `project-knowledge.yaml` via `python3 -c "import yaml; ..."`, falling back to `.set-core/.merge-strategies.json` (profile defaults, JSON format) [REQ: merge-strategy-configuration]
- [x] 3.2 Add `match_strategy()` function: given a file path, find the first matching strategy by glob pattern [REQ: merge-strategy-configuration]
- [x] 3.3 Define strategy config variables: arrays for patterns, strategy types, entity_patterns, validate_commands, llm_hints indexed by strategy number [REQ: merge-strategy-configuration]

## 4. Additive Strategy + Entity Counting

- [x] 4.1 Add `count_entities()` function: given a file and a regex pattern, count matching lines [REQ: additive-merge-strategy-with-entity-counting]
- [x] 4.2 Integrate entity counting: for "additive" strategy files, compute expected = base_count + ours_added_entities + theirs_added_entities, block if merged < expected [REQ: additive-merge-strategy-with-entity-counting]
- [x] 4.3 Log entity count results: "Entity count: base={B}, ours_added={N}, theirs_added={M}, merged={P}, expected={E}" [REQ: additive-merge-strategy-with-entity-counting]

## 5. LLM Prompt Enrichment

- [x] 5.1 Modify `llm_resolve_conflicts()` to accept strategy hints per file (injected into INPUT prompt only, output parser unchanged) [REQ: llm-prompt-enrichment-from-strategy-config]
- [x] 5.2 For files with a matched strategy, prepend `llm_hint` and strategy type to the file's section in the prompt [REQ: llm-prompt-enrichment-from-strategy-config]
- [x] 5.3 For "additive" strategy files, add standard hint: "This file uses additive merge — NEVER remove entities from either side" [REQ: additive-merge-strategy-enriches-llm-prompt]

## 6. Post-Merge Validation Commands

- [x] 6.1 After conservation + entity checks pass, run `validate_command` for matching strategies via `bash -c` [REQ: post-merge-validation-command]
- [x] 6.2 On validation failure: `git reset --merge`, log command output, exit non-zero [REQ: post-merge-validation-command]

## 7. Profile Integration

- [x] 7.1 Add `merge_strategies()` method to profile interface (returns list of strategy dicts) [REQ: profile-system-supplies-default-merge-strategies]
- [ ] 7.2 Implement default web profile strategies: Prisma schema (additive + prisma validate), middleware (additive), i18n JSON (already handled by existing pipeline) [REQ: profile-system-supplies-default-merge-strategies] — DEFERRED: lives in set-project-web package
- [ ] 7.3 Write profile strategies to `.set-core/.merge-strategies.json` (JSON format) during `set-project init` [REQ: profile-system-supplies-default-merge-strategies] — DEFERRED: lives in set-project-web package
- [x] 7.4 `load_merge_strategies()` reads profile JSON file as fallback when project-knowledge.yaml has no merge_strategies [REQ: merge-strategy-configuration]

## 8. Agent Rule — DB Type Safety

- [x] 8.1 Create `.claude/rules/web/db-type-safety.md` rule file prohibiting `any` type on DB client parameters [REQ: agent-rule-prohibiting-db-type-hacks]
- [x] 8.2 Add to `templates/` for deployment via `set-project init` [REQ: agent-rule-prohibiting-db-type-hacks]
- [x] 8.3 Update `project-knowledge.yaml` template with example `merge_strategies` section [REQ: merge-strategy-configuration]

## 9. Test Validation

- [x] 9.1 Re-run test fixture from 1.4 with conservation check enabled — verify merge is now BLOCKED when models are lost [REQ: diff-based-conservation-check-after-llm-merge]
- [x] 9.2 Test additive strategy: create a fixture with entity_pattern, verify entity count drop blocks merge [REQ: additive-merge-strategy-with-entity-counting]
- [ ] 9.3 Test validate_command: create a fixture with a failing validation command, verify merge is blocked [REQ: post-merge-validation-command] — covered by unit test function, needs E2E with real wt-merge
- [x] 9.4 Test LLM hint: verify enriched prompt contains strategy hints (inspect prompt output) [REQ: llm-prompt-enrichment-from-strategy-config]
- [ ] 9.5 Test profile fallback: verify merge strategies from profile JSON file are used when project-knowledge.yaml has none [REQ: profile-system-supplies-default-merge-strategies] — DEFERRED: needs set-project-web
- [x] 9.6 Test conservation check with clean merge (both sides preserved) — verify merge proceeds [REQ: diff-based-conservation-check-after-llm-merge]
- [ ] 9.7 Test edge case: binary file in conflict — verify conservation check skips it [REQ: conservation-check-computes-additions-from-merge-base] — needs binary file fixture
- [ ] 9.8 Test edge case: file new on both sides — verify conservation check treats base as empty [REQ: conservation-check-computes-additions-from-merge-base] — needs new-on-both fixture
- [ ] 9.9 Test --no-conservation-check flag bypasses all checks [REQ: diff-based-conservation-check-after-llm-merge] — needs E2E with real wt-merge

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN both sides add content and LLM preserves all THEN conservation check passes [REQ: diff-based-conservation-check-after-llm-merge, scenario: both-sides-add-content-and-llm-preserves-all]
- [x] AC-2: WHEN LLM drops additions from one side THEN conservation check fails with detailed log [REQ: diff-based-conservation-check-after-llm-merge, scenario: llm-drops-additions-from-one-side]
- [x] AC-3: WHEN conservation check fails THEN wt-merge resets merge and exits non-zero [REQ: diff-based-conservation-check-after-llm-merge, scenario: conservation-check-failure-blocks-merge]
- [x] AC-4: WHEN file matches additive strategy and entity count drops THEN merge is blocked [REQ: additive-merge-strategy-with-entity-counting, scenario: entity-count-drops-after-merge]
- [ ] AC-5: WHEN file matches strategy with validate_command and command fails THEN merge is blocked [REQ: post-merge-validation-command, scenario: validation-command-fails] — function tested, E2E deferred
- [x] AC-6: WHEN file matches strategy with llm_hint THEN LLM prompt includes the hint [REQ: llm-prompt-enrichment-from-strategy-config, scenario: llm-receives-file-type-hint]
- [ ] AC-7: WHEN project has no merge_strategies but profile provides defaults THEN profile defaults are used [REQ: profile-system-supplies-default-merge-strategies, scenario: profile-provides-defaults] — DEFERRED: needs set-project-web
- [x] AC-8: WHEN set-project init runs THEN db-type-safety.md rule is deployed [REQ: agent-rule-prohibiting-db-type-hacks, scenario: rule-file-exists-and-is-deployed]
- [ ] AC-9: WHEN --no-conservation-check flag is used THEN all checks are skipped [REQ: diff-based-conservation-check-after-llm-merge, scenario: bypass-via-flag] — flag implemented, E2E deferred
- [ ] AC-10: WHEN file is binary THEN conservation check skips it [REQ: conservation-check-computes-additions-from-merge-base, scenario: binary-files-are-skipped] — logic implemented, fixture deferred
- [ ] AC-11: WHEN file is new on both sides THEN base is treated as empty and both sides' content is verified [REQ: conservation-check-computes-additions-from-merge-base, scenario: file-is-new-on-both-sides] — logic implemented, fixture deferred
- [ ] AC-12: WHEN project config and profile both define strategies for same pattern THEN project config wins [REQ: profile-system-supplies-default-merge-strategies, scenario: project-config-overrides-profile-defaults] — DEFERRED: needs set-project-web
