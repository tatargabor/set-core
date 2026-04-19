---
name: openspec-verify-change
description: Verify implementation matches change artifacts. Use when the user wants to validate that implementation is complete, correct, and coherent before archiving.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

Verify that an implementation matches the change artifacts (specs, tasks, design).

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show changes that have implementation tasks (tasks artifact exists).
   Include the schema used for each change if available.
   Mark changes with incomplete tasks as "(In Progress)".

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifacts exist for this change

3. **Get the change directory and load artifacts**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns the change directory and context files. Read all available artifacts from `contextFiles`.

4. **Initialize verification report structure**

   Create a report structure with three dimensions:
   - **Completeness**: Track tasks, AC items, traceability, and spec coverage
   - **Correctness**: Track requirement implementation and scenario coverage
   - **Coherence**: Track design adherence, overshoot detection, and pattern consistency

   Each dimension can have CRITICAL, WARNING, or SUGGESTION issues.

5. **Verify Completeness**

   **Task Completion**:
   - If tasks.md exists in contextFiles, read it
   - Parse checkboxes: `- [ ]` (incomplete) vs `- [x]` (complete)
   - Count complete vs total tasks (exclude AC items from this count)
   - If incomplete tasks exist:
     - Add CRITICAL issue for each incomplete task
     - Recommendation: "Complete task: <description>" or "Mark as done if already implemented"

   **Acceptance Criteria Checking**:
   - Parse the `## Acceptance Criteria (from spec scenarios)` section from tasks.md (if present)
   - Find all `AC-N:` items and check their checkbox status
   - If unchecked AC items exist:
     - Add CRITICAL issue: "Acceptance criterion not met: <AC description>"
     - Include the source `[REQ: ..., scenario: ...]` reference in the recommendation
   - If all AC items are checked: note "Acceptance Criteria: N/N passed"
   - If section is absent: note "No acceptance criteria section — skipping AC check" (not an error)

   **Traceability Matrix**:
   - Parse `[REQ: <name>]` tags from all implementation tasks in tasks.md (case-insensitive, whitespace-tolerant)
   - Extract all `### Requirement:` headers from delta specs in `openspec/changes/<name>/specs/`
   - Build and output a traceability matrix:

     ```
     ## Traceability Matrix
     | Requirement | Tasks | Status |
     |-------------|-------|--------|
     | req-name    | 1.1, 1.3 | Covered |
     | other-req   | (none) | MISSING |
     ```

   - For each requirement with no matching task: Add CRITICAL issue "Requirement not covered by any task: <requirement name>"
   - For each `[REQ: <name>]` tag that doesn't match any spec requirement: Add WARNING "Unresolved requirement reference: <name>"
   - For each task without any `[REQ: ...]` tag: Add WARNING "Task without requirement link: <task description>"
   - If no delta specs exist: skip traceability matrix, note "No delta specs — skipping traceability check"

   **Spec Coverage**:
   - If delta specs exist in `openspec/changes/<name>/specs/`:
     - For each requirement not already flagged by traceability matrix:
       - Search codebase for implementation evidence
       - If requirement appears unimplemented:
         - Add CRITICAL issue: "Requirement not found: <requirement name>"
         - Recommendation: "Implement requirement X: <description>"

6. **Verify Correctness**

   **Requirement Implementation Mapping**:
   - For each requirement from delta specs:
     - Search codebase for implementation evidence
     - If found, note file paths and line ranges
     - Assess if implementation matches requirement intent
     - If divergence detected:
       - Add WARNING: "Implementation may diverge from spec: <details>"
       - Recommendation: "Review <file>:<lines> against requirement X"

   **Scenario Coverage**:
   - For each scenario in delta specs (marked with "#### Scenario:"):
     - Check if conditions are handled in code
     - Check if tests exist covering the scenario
     - If scenario appears uncovered:
       - Add WARNING: "Scenario not covered: <scenario name>"
       - Recommendation: "Add test or implementation for scenario: <description>"

7. **Verify Coherence**

   **Design Adherence**:
   - If design.md exists in contextFiles:
     - Extract key decisions (look for sections like "Decision:", "Approach:", "Architecture:")
     - Verify implementation follows those decisions
     - If contradiction detected:
       - Add WARNING: "Design decision not followed: <decision>"
       - Recommendation: "Update implementation or revise design.md to match reality"
   - If no design.md: Skip design adherence check, note "No design.md to verify against"

   **Scope Boundary Enforcement**:
   - For each delta spec, check for `## IN SCOPE` and `## OUT OF SCOPE` sections
   - If both sections are absent for a spec: note "No scope boundary defined for <spec> — skipping scope check"
   - If OUT OF SCOPE section exists:
     - Check implementation (diff or codebase) for evidence of implementing OUT OF SCOPE items
     - If found: Add WARNING "Out-of-scope implementation detected: <item>"
     - Recommendation: "Remove <item> or update spec scope boundary"
   - If IN SCOPE section exists:
     - Check that items listed in IN SCOPE have implementation evidence
     - If found: note as covered in the report

   **Overshoot Detection** (runs after scope boundary check):
   - If no delta specs exist: note "No delta specs — overshoot check skipped" and skip
   - Get the diff of the change branch vs merge-base (use `git diff $(git merge-base HEAD main)..HEAD` or equivalent)
   - Scan the diff for new routes, endpoints, components, exports, and database tables
   - For each new item found:
     - Check if it corresponds to a requirement in the delta specs (by name or IN SCOPE entry)
     - If IN SCOPE section is absent: fall back to checking against requirement names only
     - Use LLM judgment to distinguish implementation details (helper functions, utilities serving a spec requirement) from new user-facing features — do NOT flag internal helpers
     - If untraced: Add WARNING "Potential overshoot — new <route/component/export> not in spec: <item>"
     - Recommendation: "Remove <item> or add a spec requirement for it"
   - Overshoot severity is always WARNING, never CRITICAL
   - Add note: "Overshoot detection uses heuristics — review flagged items manually"

   **Code Pattern Consistency**:
   - Review new code for consistency with project patterns
   - Check file naming, directory structure, coding style
   - If significant deviations found:
     - Add SUGGESTION: "Code pattern deviation: <details>"
     - Recommendation: "Consider following project pattern: <example>"

   **Change-Specific Verify Hook**:
   - If `<change-dir>/verify-hook.sh` exists, run it: `bash <change-dir>/verify-hook.sh`
   - The hook owns any repository-wide gate the change wants to enforce (e.g., hardcoded-path audit, migration residuals, schema consistency)
   - Non-zero exit adds a CRITICAL issue: "Change-specific verify gate failed — see stderr above"
   - Recommendation: "Fix the residuals the hook reported, re-run the hook, then retry /opsx:verify"
   - Absence is not an error — the hook is opt-in per change

8. **Generate Verification Report**

   **Summary Scorecard**:
   ```
   ## Verification Report: <change-name>

   ### Summary
   | Dimension    | Status                         |
   |--------------|--------------------------------|
   | Completeness | X/Y tasks, N/M ACs, traceability|
   | Correctness  | M/N reqs covered               |
   | Coherence    | Followed/Issues                |
   ```

   Output the Traceability Matrix (from step 5) under the summary.

   **Issues by Priority**:

   1. **CRITICAL** (Must fix before archive):
      - Incomplete tasks
      - Unchecked acceptance criteria
      - Requirements with no task coverage
      - Missing requirement implementations
      - Each with specific, actionable recommendation

   2. **WARNING** (Should fix):
      - Spec/design divergences
      - Missing scenario coverage
      - Unresolved REQ tag references
      - Tasks without REQ tags
      - Out-of-scope implementations
      - Overshoot detections
      - Each with specific recommendation

   3. **SUGGESTION** (Nice to fix):
      - Pattern inconsistencies
      - Minor improvements
      - Each with specific recommendation

   **Final Assessment**:
   - If CRITICAL issues: "X critical issue(s) found. Fix before archiving."
   - If only warnings: "No critical issues. Y warning(s) to consider. Ready for archive (with noted improvements)."
   - If all clear: "All checks passed. Ready for archive."

   **End with sentinel**:
   Output exactly one of these on its own line at the very end of the report:
   - `VERIFY_RESULT: PASS` — if no CRITICAL issues
   - `VERIFY_RESULT: FAIL` — if any CRITICAL issues exist

**Verification Heuristics**

- **Completeness**: Focus on objective checklist items (checkboxes, requirements list, REQ tags)
- **Correctness**: Use keyword search, file path analysis, reasonable inference - don't require perfect certainty
- **Coherence**: Look for glaring inconsistencies, don't nitpick style
- **False Positives**: When uncertain, prefer SUGGESTION over WARNING, WARNING over CRITICAL
- **Actionability**: Every issue must have a specific recommendation with file/line references where applicable
- **Overshoot**: Helper functions and utilities that serve a spec requirement are NOT overshoot — only flag new user-facing features, routes, or exports with no spec backing

**Graceful Degradation**

- If only tasks.md exists: verify task completion only, skip spec/design/traceability checks
- If tasks + specs exist: verify completeness (including traceability) and correctness, skip design
- If full artifacts: verify all three dimensions including overshoot
- Always note which checks were skipped and why

**Output Format**

Use clear markdown with:
- Table for summary scorecard
- Traceability Matrix as a markdown table
- Grouped lists for issues (CRITICAL/WARNING/SUGGESTION)
- Code references in format: `file.ts:123`
- Specific, actionable recommendations
- No vague suggestions like "consider reviewing"
- `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` as the final line
