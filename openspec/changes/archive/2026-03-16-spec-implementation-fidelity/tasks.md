## 1. Spec Template — Scope Boundary

- [x] 1.1 Add IN SCOPE / OUT OF SCOPE section to the spec artifact template in openspec CLI — update the `template` field returned by `openspec instructions specs` to include the new section after preamble, before Requirements [REQ: spec-template-includes-scope-boundary-section]
- [x] 1.2 Update the `instruction` field for the specs artifact to guide agents on filling IN SCOPE (bullet list of included functionality) and OUT OF SCOPE (bullet list of explicitly excluded functionality) [REQ: spec-template-includes-scope-boundary-section]
- [x] 1.3 Update the apply-change skill (`.claude/skills/openspec-apply-change/SKILL.md`) to instruct agents to read IN SCOPE / OUT OF SCOPE from delta specs and only implement items in IN SCOPE [REQ: verify-skill-enforces-scope-boundary]

## 2. Task Traceability in FF Skill

- [x] 2.1 Update the ff-change skill (`.claude/skills/openspec-ff-change/SKILL.md`) instruction for tasks artifact to require `[REQ: <requirement-name>]` tags (kebab-case slug of requirement header) on each implementation task, with case-insensitive and whitespace-tolerant matching [REQ: tasks-reference-requirement-ids]
- [x] 2.2 Add instruction in the ff-change skill to generate an `## Acceptance Criteria (from spec scenarios)` section at the bottom of tasks.md, extracting WHEN/THEN scenarios from delta specs as checkbox items with format `- [ ] AC-N: WHEN <condition> THEN <outcome> [REQ: <name>, scenario: <scenario-name>]` [REQ: ff-skill-generates-acceptance-criteria-from-scenarios]

## 3. Verify Skill — Bidirectional Checking

- [x] 3.1 Add traceability matrix generation to the verify-change skill (`SKILL.md`): parse `[REQ: ...]` tags from tasks.md (kebab-case, case-insensitive), cross-reference against delta spec `### Requirement:` headers, output a Requirement/Tasks/Status table; report CRITICAL for missing requirements, WARNING for unresolved REQ references [REQ: verify-generates-traceability-matrix]
- [x] 3.2 Add scope boundary enforcement to the verify-change skill: read IN SCOPE / OUT OF SCOPE from delta specs, flag implementation matching OUT OF SCOPE items as WARNING; skip gracefully if sections are absent [REQ: verify-skill-enforces-scope-boundary]
- [x] 3.3 Add overshoot detection to the verify-change skill (complete 3.2 first — both modify the same SKILL.md): scan diff for new routes, endpoints, components, exports; check each against spec requirements; flag untraced items as WARNING (not CRITICAL); use LLM judgment to distinguish implementation details from new features [REQ: verify-skill-detects-implementation-overshoot]
- [x] 3.4 Add acceptance criteria checking to the verify-change skill: parse `## Acceptance Criteria` section, treat unchecked `AC-N` items as CRITICAL (same as unchecked tasks); skip gracefully if section absent or empty [REQ: verify-treats-unchecked-acceptance-criteria-as-critical]
- [x] 3.5 Handle overshoot detection edge cases in the verify-change skill: skip overshoot check with a note when no delta specs exist; fall back to requirement-name-only matching when delta specs are present but lack IN SCOPE sections (complete 3.3 first) [REQ: overshoot-check-integrates-with-existing-verify-flow]

## 4. Verifier.py — Soft-Pass Fix

- [x] 4.1 Replace the soft-pass logic in `verifier.py` `handle_change_done()` (search for "soft-pass" comment): when VERIFY_RESULT sentinel is missing, set `spec_coverage_result = "timeout"` and `verify_ok = False` instead of auto-passing based on other gates [REQ: vg-pipeline]
- [x] 4.2 Increase spec verify max-turns from 15 to 20 in the `run_claude()` call in `handle_change_done()` spec verify section [REQ: vg-pipeline]

## 5. Review Prompt — Overshoot Instruction

- [x] 5.1 Update `build_req_review_section()` in `verifier.py` to append an "Overshoot Check" instruction block telling the reviewer to flag new routes/endpoints/components not traceable to assigned requirements as [WARNING] [REQ: vr-req]
- [x] 5.2 Verify that `run_claude()` review call in `handle_change_done()` includes the updated review prompt from `build_req_review_section()` — no change needed if already wired, otherwise ensure the overshoot instruction reaches the LLM reviewer [REQ: vr-review]

## 6. Plan Completeness Check

- [x] 6.1 Add reverse requirement coverage check to `validate_plan()` in `planner.py` (complete 6.2 first — uses the parsed deferred_requirement_ids): compute `unassigned = all_digest_reqs - (all change requirements[] ∪ all change also_affects_reqs[])`, then subtract `deferred_requirement_ids`; report remaining as errors [REQ: plan-validation-checks-reverse-requirement-coverage]
- [x] 6.2 Add `deferred_requirements` parsing to `validate_plan()`: read the optional array from plan JSON, validate each entry has `id` and `reason`, report informational warnings for deferred items, warn if deferred ID not found in digest [REQ: plan-schema-supports-deferred-requirements]
- [x] 6.3 Update the decompose skill (`.claude/skills/wt/decompose/SKILL.md`) prompt to instruct the planner to account for every digest requirement — either assign to a change or list in `deferred_requirements` with reason [REQ: decompose-skill-requires-explicit-requirement-accounting]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an agent creates a spec file using `openspec instructions specs` THEN the template includes an IN SCOPE / OUT OF SCOPE section [REQ: spec-template-includes-scope-boundary-section, scenario: new-spec-created-with-scope-boundary]
- [x] AC-2: WHEN the verify skill processes a spec lacking IN SCOPE / OUT OF SCOPE THEN it skips scope boundary checking and notes the skip [REQ: verify-skill-enforces-scope-boundary, scenario: existing-spec-without-scope-boundary]
- [x] AC-3: WHEN the verify skill detects implementation matching an OUT OF SCOPE item THEN it reports a WARNING [REQ: verify-skill-enforces-scope-boundary, scenario: implementation-matches-out-of-scope-item]
- [x] AC-4: WHEN the ff-change skill generates tasks.md from specs THEN each task includes a `[REQ: <name>]` tag [REQ: tasks-reference-requirement-ids, scenario: task-generated-with-requirement-tag]
- [x] AC-5: WHEN the verify skill finds a task without `[REQ: ...]` tag THEN it reports a WARNING [REQ: tasks-reference-requirement-ids, scenario: task-without-requirement-tag-detected-by-verify]
- [x] AC-6: WHEN a spec requirement has no corresponding task THEN the verify skill reports CRITICAL [REQ: verify-generates-traceability-matrix, scenario: uncovered-requirement-in-matrix]
- [x] AC-7: WHEN all delta spec requirements have matching tasks THEN the traceability matrix shows all with status "Covered" [REQ: verify-generates-traceability-matrix, scenario: all-requirements-covered]
- [x] AC-8: WHEN the traceability matrix is generated THEN it appears as a markdown table under "## Traceability Matrix" with columns Requirement, Tasks, Status [REQ: verify-generates-traceability-matrix, scenario: matrix-output-format]
- [x] AC-9: WHEN the verify skill finds a `[REQ: ...]` tag not matching any spec requirement THEN it reports a WARNING [REQ: tasks-reference-requirement-ids, scenario: unresolved-requirement-reference-in-task]
- [x] AC-10: WHEN the verify skill scans the diff and finds a new route not in spec THEN it reports a WARNING [REQ: verify-skill-detects-implementation-overshoot, scenario: new-route-without-spec-requirement]
- [x] AC-11: WHEN overshoot is detected THEN severity is WARNING not CRITICAL [REQ: verify-skill-detects-implementation-overshoot, scenario: overshoot-severity-is-warning-not-critical]
- [x] AC-12: WHEN no delta specs exist for overshoot check THEN it is skipped with a note [REQ: overshoot-check-integrates-with-existing-verify-flow, scenario: no-delta-specs-available]
- [x] AC-13: WHEN spec verify output lacks VERIFY_RESULT sentinel THEN spec_coverage_result is set to "timeout" and verify_ok is False [REQ: vg-pipeline, scenario: spec-verify-missing-sentinel-treated-as-timeout-fail]
- [x] AC-14: WHEN delta specs contain WHEN/THEN scenarios THEN tasks.md includes an Acceptance Criteria section with checkbox items [REQ: ff-skill-generates-acceptance-criteria-from-scenarios, scenario: spec-with-scenarios-generates-acceptance-criteria]
- [x] AC-15: WHEN the verify skill finds unchecked AC-N items THEN it reports CRITICAL [REQ: verify-treats-unchecked-acceptance-criteria-as-critical, scenario: unchecked-acceptance-criteria]
- [x] AC-16: WHEN all digest requirements are assigned to changes THEN validate_plan() reports no coverage errors [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: all-requirements-assigned-to-changes]
- [x] AC-17: WHEN a requirement is missing from all changes but listed in deferred_requirements THEN validate_plan() adds a warning but no error [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: requirement-missing-but-deferred]
- [x] AC-18: WHEN a requirement is missing from all changes and NOT deferred THEN validate_plan() adds an error [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: requirement-missing-and-not-deferred]
- [x] AC-19: WHEN validate_plan() runs without a digest_dir THEN reverse coverage check is skipped [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: no-digest-directory-provided]
- [x] AC-20: WHEN `build_req_review_section()` is called with assigned requirements THEN the review prompt includes an "Overshoot Check" instruction [REQ: vr-req, scenario: review-prompt-includes-overshoot-instruction]
- [x] AC-21: WHEN the decompose skill generates a plan and defers requirements THEN those appear in deferred_requirements with reasons [REQ: decompose-skill-requires-explicit-requirement-accounting, scenario: planner-defers-requirements-with-reason]
- [x] AC-22: WHEN the spec verify gate invokes /opsx:verify THEN the max-turns parameter is 20 [REQ: vg-pipeline, scenario: spec-verify-with-increased-max-turns]
- [x] AC-23: WHEN the apply skill reads a spec with IN SCOPE / OUT OF SCOPE THEN it instructs the agent to implement only IN SCOPE items [REQ: verify-skill-enforces-scope-boundary, scenario: agent-prompt-includes-scope-constraint]
- [x] AC-24: WHEN delta specs have no WHEN/THEN scenarios THEN the ff-change skill generates tasks.md without an Acceptance Criteria section [REQ: ff-skill-generates-acceptance-criteria-from-scenarios, scenario: spec-without-scenarios]
- [x] AC-25: WHEN the verify skill finds all AC-N items checked THEN it reports no AC-related issues [REQ: verify-treats-unchecked-acceptance-criteria-as-critical, scenario: all-acceptance-criteria-checked]
- [x] AC-26: WHEN tasks.md has no Acceptance Criteria section THEN the verify skill skips AC checking gracefully [REQ: verify-treats-unchecked-acceptance-criteria-as-critical, scenario: no-acceptance-criteria-section-in-tasks-md]
- [x] AC-27: WHEN a deferred_requirements entry's ID does not match any digest requirement THEN validate_plan() adds a warning [REQ: plan-schema-supports-deferred-requirements, scenario: deferred-requirement-id-not-found-in-digest]
- [x] AC-28: WHEN the verify skill finds a new route/endpoint that corresponds to a spec requirement THEN no overshoot warning is generated for that route [REQ: verify-skill-detects-implementation-overshoot, scenario: new-route-matches-spec-requirement]
- [x] AC-29: WHEN the verify skill detects new internal helper functions serving a spec requirement THEN no overshoot warning is generated [REQ: verify-skill-detects-implementation-overshoot, scenario: helper-functions-and-internal-utilities]
- [x] AC-30: WHEN the verify skill runs overshoot detection and delta specs exist but lack IN SCOPE sections THEN it falls back to checking against requirement names only [REQ: overshoot-check-integrates-with-existing-verify-flow, scenario: no-in-scope-section-available]
- [x] AC-31: WHEN the verify skill detects implementation of an IN SCOPE item THEN that item is marked as covered in the report [REQ: verify-skill-enforces-scope-boundary, scenario: implementation-within-scope]
- [x] AC-32: WHEN the LLM code reviewer processes a diff with a new route matching assigned requirements THEN no overshoot warnings appear [REQ: vr-review, scenario: reviewer-passes-clean-diff]
- [x] AC-33: WHEN the LLM code reviewer processes a diff containing a new route not in assigned requirements THEN the review output includes a [WARNING] flag [REQ: vr-review, scenario: reviewer-flags-overshoot-in-diff]
- [x] AC-34: WHEN the ff-change skill creates tasks.md and multiple delta specs contain scenarios THEN all scenarios are included and grouped by requirement name [REQ: ff-skill-generates-acceptance-criteria-from-scenarios, scenario: multiple-specs-with-scenarios]
- [x] AC-35: WHEN the planner generates a plan and all requirements are assigned to changes THEN deferred_requirements is empty or omitted and validate_plan() passes [REQ: plan-schema-supports-deferred-requirements, scenario: plan-without-deferred-requirements-field]
- [x] AC-36: WHEN a spec requirement has no corresponding task (checked under tasks-reference-requirement-ids) THEN the verify skill reports CRITICAL [REQ: tasks-reference-requirement-ids, scenario: requirement-with-no-tasks-detected-by-verify]
- [x] AC-37: WHEN build_req_review_section() is called with an empty requirements[] or no digest THEN the returned section is empty and no overshoot instruction is included [REQ: vr-req, scenario: no-requirements-assigned-skips-overshoot-instruction]
- [x] AC-38: WHEN the planner generates a plan with a deferred_requirements array THEN each entry contains both id and reason fields [REQ: plan-schema-supports-deferred-requirements, scenario: plan-with-deferred-requirements-field]
- [x] AC-39: WHEN the decompose skill generates a plan and assigns all requirements to changes THEN deferred_requirements is empty or omitted and validate_plan() reports no coverage errors [REQ: decompose-skill-requires-explicit-requirement-accounting, scenario: planner-assigns-all-requirements]
