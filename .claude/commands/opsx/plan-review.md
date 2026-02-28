---
name: "OPSX: Plan Review"
description: "Review a spec document against the planning guide and checklist"
category: Workflow
tags: [workflow, planning, review, orchestration]
---

Review a spec document against the orchestration planning guide and checklist.

**Input**: The argument after `/opsx:plan-review` is the path to the spec file to review. If no path is given, ask the user which file to review.

**Steps**

1. **Read the planning guide and checklist**
   - Read `docs/planning-guide.md` from the wt-tools project (find it via `which wt-orchestrate` → resolve to wt-tools root, or check common locations: `~/code2/wt-tools/docs/`, `~/code/wt-tools/docs/`)
   - Read `docs/plan-checklist.md` from the same location
   - If not found locally, check if the current project has copies in its own `docs/` directory

2. **Read the spec document**
   - Read the file path provided by the user
   - If no path given, use AskUserQuestion to ask

3. **Review against the checklist**

   Go through each checklist category and evaluate the spec:

   **Scope & Overlap**
   - Are scopes self-contained? Any shared files between parallel items?
   - Are scopes specific enough (not vague)?
   - Any L-sized items that should be split?

   **Dependencies**
   - Are schema migrations sequential?
   - Is auth foundational?
   - Are shared type changes identified?
   - Any missing implicit dependencies (barrel exports, config files)?

   **Testing**
   - Does each item mention what to test?
   - Is test infrastructure addressed?
   - Are existing test patterns referenced?

   **Sizing & Phases**
   - Is the batch size reasonable (4-6 per phase)?
   - Are phases marked if >6 items?
   - Are phases independently valuable?

   **Directives**
   - Are orchestrator directives present?
   - Is `test_command` set?
   - Is `merge_policy` appropriate?

   **Design Rules (Layer Check)**
   - Layer 1 (Business Intent): Is the "what" clear for each item?
   - Layer 2 (Constraints): Are boundaries, validation rules, access control specified?
   - Layer 3 (Solution Shape): Are selective choices (libraries, UI patterns) reasonable?
   - Layer 4 (Implementation): Is anything over-specified that should be left to the agent?

   **Spec-Writing Checklist per Feature**
   For each feature, check:
   - What data does it read/write?
   - Who can access it?
   - What happens on error?
   - Happy path AND edge cases covered?
   - Does it interact with existing features?
   - What's the UI entry point?

4. **Output the review**

   Format:

   ```
   ## Plan Review: <filename>

   ### Summary
   <1-2 sentence overall assessment>

   ### Checklist Results

   #### Scope & Overlap
   - [x] or [ ] for each item, with notes

   #### Dependencies
   ...

   #### Testing
   ...

   #### Sizing & Phases
   ...

   #### Directives
   ...

   ### Per-Feature Review

   **<Feature 1>**
   - Layers: ✅ Intent, ✅ Constraints, ⚠️ Missing error handling, ✅ Not over-specified
   - Data: specified / missing
   - Access: specified / missing
   - Tests: specified / missing
   - Suggestion: <specific improvement>

   **<Feature 2>**
   ...

   ### Suggested Improvements
   1. <Concrete, actionable suggestion>
   2. <Concrete, actionable suggestion>
   ...
   ```

5. **Offer to help fix**
   After the review, ask if the user wants help fixing specific issues in the spec.

**Guardrails**
- Be specific — don't just say "scope is vague", say "this item doesn't specify what happens when the CSV has invalid emails"
- Reference the planning guide sections by name when making suggestions
- Don't rewrite the spec — point out what to improve and let the user decide
- Be encouraging about what IS well-specified, not just critical
