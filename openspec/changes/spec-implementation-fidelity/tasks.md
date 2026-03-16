## 1. Spec Template — Scope Boundary

- [ ] 1.1 Add IN SCOPE / OUT OF SCOPE section to the spec artifact template in openspec CLI — update the `template` field returned by `openspec instructions specs` to include the new section after preamble, before Requirements [REQ: spec-template-includes-scope-boundary-section]
- [ ] 1.2 Update the `instruction` field for the specs artifact to guide agents on filling IN SCOPE (bullet list of included functionality) and OUT OF SCOPE (bullet list of explicitly excluded functionality) [REQ: spec-template-includes-scope-boundary-section]
- [ ] 1.3 Update the apply-change skill (`.claude/skills/openspec-apply-change/SKILL.md`) to instruct agents to read IN SCOPE / OUT OF SCOPE from delta specs and only implement items in IN SCOPE [REQ: verify-skill-enforces-scope-boundary]

## 2. Task Traceability in FF Skill

- [ ] 2.1 Update the ff-change skill (`.claude/skills/openspec-ff-change/SKILL.md`) instruction for tasks artifact to require `[REQ: <requirement-name>]` tags (kebab-case slug of requirement header) on each implementation task, with case-insensitive and whitespace-tolerant matching [REQ: tasks-reference-requirement-ids]
- [ ] 2.2 Add instruction in the ff-change skill to generate an `## Acceptance Criteria (from spec scenarios)` section at the bottom of tasks.md, extracting WHEN/THEN scenarios from delta specs as checkbox items with format `- [ ] AC-N: WHEN <condition> THEN <outcome> [REQ: <name>, scenario: <scenario-name>]` [REQ: ff-skill-generates-acceptance-criteria-from-scenarios]

## 3. Verify Skill — Bidirectional Checking

- [ ] 3.1 Add traceability matrix generation to the verify-change skill (`SKILL.md`): parse `[REQ: ...]` tags from tasks.md (kebab-case, case-insensitive), cross-reference against delta spec `### Requirement:` headers, output a Requirement/Tasks/Status table; report CRITICAL for missing requirements, WARNING for unresolved REQ references [REQ: verify-generates-traceability-matrix]
- [ ] 3.2 Add scope boundary enforcement to the verify-change skill: read IN SCOPE / OUT OF SCOPE from delta specs, flag implementation matching OUT OF SCOPE items as WARNING; skip gracefully if sections are absent [REQ: verify-skill-enforces-scope-boundary]
- [ ] 3.3 Add overshoot detection to the verify-change skill (complete 3.2 first — both modify the same SKILL.md): scan diff for new routes, endpoints, components, exports; check each against spec requirements; flag untraced items as WARNING (not CRITICAL); use LLM judgment to distinguish implementation details from new features [REQ: verify-skill-detects-implementation-overshoot]
- [ ] 3.4 Add acceptance criteria checking to the verify-change skill: parse `## Acceptance Criteria` section, treat unchecked `AC-N` items as CRITICAL (same as unchecked tasks); skip gracefully if section absent or empty [REQ: verify-treats-unchecked-acceptance-criteria-as-critical]

## 4. Verifier.py — Soft-Pass Fix

- [ ] 4.1 Replace the soft-pass logic in `verifier.py` `handle_change_done()` (search for "soft-pass" comment): when VERIFY_RESULT sentinel is missing, set `spec_coverage_result = "timeout"` and `verify_ok = False` instead of auto-passing based on other gates [REQ: vg-pipeline]
- [ ] 4.2 Increase spec verify max-turns from 15 to 20 in the `run_claude()` call in `handle_change_done()` spec verify section [REQ: vg-pipeline]

## 5. Review Prompt — Overshoot Instruction

- [ ] 5.1 Update `build_req_review_section()` in `verifier.py` to append an "Overshoot Check" instruction block telling the reviewer to flag new routes/endpoints/components not traceable to assigned requirements as [WARNING] [REQ: vr-req]

## 6. Plan Completeness Check

- [ ] 6.1 Add reverse requirement coverage check to `validate_plan()` in `planner.py` (complete 6.2 first — uses the parsed deferred_requirement_ids): compute `unassigned = all_digest_reqs - (all change requirements[] ∪ all change also_affects_reqs[])`, then subtract `deferred_requirement_ids`; report remaining as errors [REQ: plan-validation-checks-reverse-requirement-coverage]
- [ ] 6.2 Add `deferred_requirements` parsing to `validate_plan()`: read the optional array from plan JSON, validate each entry has `id` and `reason`, report informational warnings for deferred items, warn if deferred ID not found in digest [REQ: plan-schema-supports-deferred-requirements]
- [ ] 6.3 Update the decompose skill (`.claude/skills/wt/decompose/SKILL.md`) prompt to instruct the planner to account for every digest requirement — either assign to a change or list in `deferred_requirements` with reason [REQ: decompose-skill-requires-explicit-requirement-accounting]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN an agent creates a spec file using `openspec instructions specs` THEN the template includes an IN SCOPE / OUT OF SCOPE section [REQ: spec-template-includes-scope-boundary-section, scenario: new-spec-created-with-scope-boundary]
- [ ] AC-2: WHEN the verify skill processes a spec lacking IN SCOPE / OUT OF SCOPE THEN it skips scope boundary checking and notes the skip [REQ: verify-skill-enforces-scope-boundary, scenario: existing-spec-without-scope-boundary]
- [ ] AC-3: WHEN the verify skill detects implementation matching an OUT OF SCOPE item THEN it reports a WARNING [REQ: verify-skill-enforces-scope-boundary, scenario: implementation-matches-out-of-scope-item]
- [ ] AC-4: WHEN the ff-change skill generates tasks.md from specs THEN each task includes a `[REQ: <name>]` tag [REQ: tasks-reference-requirement-ids, scenario: task-generated-with-requirement-tag]
- [ ] AC-5: WHEN the verify skill finds a task without `[REQ: ...]` tag THEN it reports a WARNING [REQ: tasks-reference-requirement-ids, scenario: task-without-requirement-tag-detected-by-verify]
- [ ] AC-6: WHEN a spec requirement has no corresponding task THEN the verify skill reports CRITICAL [REQ: verify-generates-traceability-matrix, scenario: uncovered-requirement-in-matrix]
- [ ] AC-7: WHEN all delta spec requirements have matching tasks THEN the traceability matrix shows all with status "Covered" [REQ: verify-generates-traceability-matrix, scenario: all-requirements-covered]
- [ ] AC-8: WHEN the traceability matrix is generated THEN it appears as a markdown table under "## Traceability Matrix" with columns Requirement, Tasks, Status [REQ: verify-generates-traceability-matrix, scenario: matrix-output-format]
- [ ] AC-9: WHEN the verify skill finds a `[REQ: ...]` tag not matching any spec requirement THEN it reports a WARNING [REQ: tasks-reference-requirement-ids, scenario: unresolved-requirement-reference-in-task]
- [ ] AC-10: WHEN the verify skill scans the diff and finds a new route not in spec THEN it reports a WARNING [REQ: verify-skill-detects-implementation-overshoot, scenario: new-route-without-spec-requirement]
- [ ] AC-11: WHEN overshoot is detected THEN severity is WARNING not CRITICAL [REQ: verify-skill-detects-implementation-overshoot, scenario: overshoot-severity-is-warning-not-critical]
- [ ] AC-12: WHEN no delta specs exist for overshoot check THEN it is skipped with a note [REQ: overshoot-check-integrates-with-existing-verify-flow, scenario: no-delta-specs-available]
- [ ] AC-13: WHEN spec verify output lacks VERIFY_RESULT sentinel THEN spec_coverage_result is set to "timeout" and verify_ok is False [REQ: vg-pipeline, scenario: spec-verify-missing-sentinel-treated-as-timeout-fail]
- [ ] AC-14: WHEN delta specs contain WHEN/THEN scenarios THEN tasks.md includes an Acceptance Criteria section with checkbox items [REQ: ff-skill-generates-acceptance-criteria-from-scenarios, scenario: spec-with-scenarios-generates-acceptance-criteria]
- [ ] AC-15: WHEN the verify skill finds unchecked AC-N items THEN it reports CRITICAL [REQ: verify-treats-unchecked-acceptance-criteria-as-critical, scenario: unchecked-acceptance-criteria]
- [ ] AC-16: WHEN all digest requirements are assigned to changes THEN validate_plan() reports no coverage errors [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: all-requirements-assigned-to-changes]
- [ ] AC-17: WHEN a requirement is missing from all changes but listed in deferred_requirements THEN validate_plan() adds a warning but no error [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: requirement-missing-but-deferred]
- [ ] AC-18: WHEN a requirement is missing from all changes and NOT deferred THEN validate_plan() adds an error [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: requirement-missing-and-not-deferred]
- [ ] AC-19: WHEN validate_plan() runs without a digest_dir THEN reverse coverage check is skipped [REQ: plan-validation-checks-reverse-requirement-coverage, scenario: no-digest-directory-provided]
- [ ] AC-20: WHEN `build_req_review_section()` is called with assigned requirements THEN the review prompt includes an "Overshoot Check" instruction [REQ: vr-req, scenario: review-prompt-includes-overshoot-instruction]
- [ ] AC-21: WHEN the decompose skill generates a plan and defers requirements THEN those appear in deferred_requirements with reasons [REQ: decompose-skill-requires-explicit-requirement-accounting, scenario: planner-defers-requirements-with-reason]
- [ ] AC-22: WHEN the spec verify gate invokes /opsx:verify THEN the max-turns parameter is 20 [REQ: vg-pipeline, scenario: spec-verify-with-increased-max-turns]
- [ ] AC-23: WHEN the apply skill reads a spec with IN SCOPE / OUT OF SCOPE THEN it instructs the agent to implement only IN SCOPE items [REQ: verify-skill-enforces-scope-boundary, scenario: agent-prompt-includes-scope-constraint]
- [ ] AC-24: WHEN delta specs have no WHEN/THEN scenarios THEN the ff-change skill generates tasks.md without an Acceptance Criteria section [REQ: ff-skill-generates-acceptance-criteria-from-scenarios, scenario: spec-without-scenarios]
- [ ] AC-25: WHEN the verify skill finds all AC-N items checked THEN it reports no AC-related issues [REQ: verify-treats-unchecked-acceptance-criteria-as-critical, scenario: all-acceptance-criteria-checked]
- [ ] AC-26: WHEN tasks.md has no Acceptance Criteria section THEN the verify skill skips AC checking gracefully [REQ: verify-treats-unchecked-acceptance-criteria-as-critical, scenario: no-acceptance-criteria-section-in-tasks-md]
- [ ] AC-27: WHEN a deferred_requirements entry's ID does not match any digest requirement THEN validate_plan() adds a warning [REQ: plan-schema-supports-deferred-requirements, scenario: deferred-requirement-id-not-found-in-digest]
