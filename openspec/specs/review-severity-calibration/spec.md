## ADDED Requirements

### Requirement: Explicit severity rubric in review prompt
The review template at `lib/set_orch/templates.py::render_review_prompt` SHALL include an explicit severity rubric that defines what qualifies as CRITICAL, HIGH, MEDIUM, and LOW — with concrete examples for each level. Currently the template asks the reviewer to "classify severity" without telling it what the tiers mean, so Opus defaults to an aggressive calibration where UI polish, design-system violations, and stylistic issues all land as CRITICAL.

Observed on minishop-run-20260412-0103: 46 review findings across 6 changes, 18 flagged CRITICAL. Inspection of the findings showed:
- ~6 CRITICAL findings were genuine security/data-loss issues (bcrypt in middleware, open admin registration, `/api/test-seed` exposing password hashes, missing prisma db push)
- ~12 CRITICAL findings were design-system or completeness issues (raw `<button>` vs shadcn Button, missing trailing newline, locale mismatch in formatPrice, raw `<span>` for badge)

The latter group should have been MEDIUM or HIGH. The reviewer is not wrong in flagging them — they are real violations of planning_rules — but CRITICAL is a merge-blocker and should be reserved for issues that would crash, leak, or destroy data.

#### Scenario: Review prompt explicitly lists severity examples
- **WHEN** `render_review_prompt()` renders the reviewer brief
- **THEN** the prompt includes a "## Severity Rubric" section containing:
  - **CRITICAL** — will crash the app, expose secrets, leak other users' data, allow privilege escalation, or cause data loss. Examples: SQL injection, missing auth on admin routes, password hash exposure, middleware imports that crash Edge Runtime, race conditions that double-charge payments.
  - **HIGH** — will produce incorrect output or broken UX in a primary user path. Examples: checkout total calculation off by cents, cart badge shows wrong count, form submits but shows success on error, product search returns stale data.
  - **MEDIUM** — violates a project rule or convention without breaking core functionality. Examples: raw `<button>` instead of shadcn Button, hardcoded color instead of design token, missing error handling on non-critical paths, fragile test selectors.
  - **LOW** — code hygiene, accessibility gaps in secondary views, missing trailing newlines, outdated comments, minor performance. Examples: `div` instead of semantic element, inline styles, console.log left in, missing alt text on decorative images.
- **THEN** the reviewer is explicitly instructed: "When in doubt between two tiers, pick the LOWER one. Escalation to CRITICAL requires that the issue makes the code unusable, insecure, or lossy in a primary path."

#### Scenario: Reviewer evaluates a shadcn Button violation
- **WHEN** the reviewer finds `<button className="...">` in a variant selector (should be `<Button variant="outline">`)
- **THEN** the reviewer classifies this as MEDIUM per the rubric (violates `components.json` convention, does not break functionality)
- **THEN** the fast-path regex OR classifier counts this as 1 medium_count, not critical_count
- **THEN** the gate passes (medium is non-blocking)

#### Scenario: Reviewer evaluates a real security issue
- **WHEN** the reviewer finds `bcryptjs` imported in `middleware.ts`
- **THEN** the reviewer classifies this as CRITICAL per the rubric (will crash Edge Runtime at deploy time = app unusable in a primary path)
- **THEN** the gate blocks the merge
- **THEN** the retry context for the agent explicitly says "CRITICAL: Edge Runtime crash — swap bcryptjs for jose for JWT verification in middleware"

### Requirement: Classifier rubric matches review prompt
The `_build_classifier_prompt()` in `lib/set_orch/llm_verdict.py` SHALL include the same severity rubric (condensed form). When the classifier sees a finding that is ambiguous between tiers, it SHALL default to the LOWER tier. This matches the review prompt's own calibration so the two paths produce consistent verdicts.

The existing `scope_context` parameter added in commit `76cb60bd` already handles out-of-scope false positives. This new change handles the in-scope but mis-calibrated severity case.

#### Scenario: Classifier sees a review text with unclear severity tags
- **WHEN** the review output says `ISSUE: Shadcn Button not used in variant selector` with no explicit severity marker
- **THEN** the classifier evaluates per the rubric and assigns MEDIUM (convention violation, not a crash)
- **THEN** the JSON response has `critical_count: 0, medium_count: 1`
- **THEN** the gate does not block

#### Scenario: Classifier sees a review text with mismatched severity
- **WHEN** the review output says `ISSUE: [CRITICAL] shadcn Badge removed from listing page`
- **THEN** the classifier recognizes the explicit `[CRITICAL]` tag but ALSO applies the severity rubric
- **THEN** per the rubric, "missing design-system component" is MEDIUM
- **THEN** the classifier emits a finding with `severity: MEDIUM` and a `note: "downgraded from reviewer-tagged CRITICAL per severity rubric — no crash/leak/data-loss impact"` field
- **THEN** the critical_count is 0, merge proceeds

### Requirement: Agents' fix prompts reflect severity
When the review gate fails and the agent is retried with `prompt_prefix` in `review_change()`, the retry prompt SHALL list only the CRITICAL and HIGH findings as "must fix", with MEDIUM and LOW findings shown as "should fix if trivial". This prevents the agent from spending retry cycles on cosmetic issues at the expense of real bugs.

#### Scenario: Retry prompt with mixed severities
- **WHEN** the review gate fails with 1 CRITICAL + 3 MEDIUM + 2 LOW findings
- **THEN** the retry context sent to the agent contains:
  - A `## Must Fix` section with the 1 CRITICAL
  - A `## Should Fix (if trivial)` section with the 3 MEDIUM
  - A `## Nice to Have` section with the 2 LOW
- **THEN** the agent is instructed: "Focus on Must Fix first. Move to Should Fix only if there is capacity. Skip Nice to Have unless the fix is a one-line change."

#### Scenario: Retry prompt with only CRITICAL
- **WHEN** the review gate fails with 3 CRITICAL findings and no lower-severity findings
- **THEN** only the `## Must Fix` section is rendered
- **THEN** the agent's focus is unambiguous

### Requirement: Severity downgrade audit trail
When the classifier downgrades a finding's severity (e.g., reviewer said CRITICAL, classifier says MEDIUM per rubric), the downgrade SHALL be recorded in the `<session_id>.verdict.json` sidecar under a `downgrades` field. This lets the operator audit whether the calibration is working as intended.

#### Scenario: Downgrade recorded in sidecar
- **WHEN** the classifier downgrades 2 findings from CRITICAL to MEDIUM
- **THEN** the sidecar includes `"downgrades": [{"from": "CRITICAL", "to": "MEDIUM", "summary": "Raw button in variant selector"}, ...]`
- **THEN** the sidecar's `source` field is `classifier_downgrade` (distinct from `classifier_override` which raises severity)
- **THEN** the operator can grep across sidecars to see how often downgrade fires and whether it correlates with actual false positives
