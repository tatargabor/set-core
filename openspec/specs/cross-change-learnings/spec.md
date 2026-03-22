## IN SCOPE
- Inject cross-change review learnings into input.md at dispatch time
- Cluster and deduplicate findings for compact representation
- Only inject during apply phase (code implementation), not ff phase

## OUT OF SCOPE
- Modifying loop_prompt.py (iteration-level injection)
- Modifying the review gate itself
- Real-time mid-loop updates (dispatch-time snapshot is sufficient)
- The learnings-to-rules pipeline (separate change)

### Requirement: Cross-change learnings injected at dispatch
When dispatching a change, the dispatcher SHALL read `review-findings.jsonl`, extract findings from OTHER changes (excluding the current change), cluster recurring patterns, and inject a compact summary into `input.md`.

#### Scenario: Sibling change had CRITICAL findings
- **GIVEN** change A completed review with CRITICAL "No auth middleware on /api/orders"
- **AND** change B is being dispatched
- **WHEN** input.md is generated for change B
- **THEN** input.md SHALL contain a "Lessons from Prior Changes" section
- **AND** the section SHALL mention the auth middleware pattern

#### Scenario: No prior findings exist
- **GIVEN** no review-findings.jsonl exists or it is empty
- **WHEN** a change is dispatched
- **THEN** input.md SHALL NOT contain a "Lessons from Prior Changes" section

#### Scenario: Only own findings exist
- **GIVEN** review-findings.jsonl only contains findings for the current change (redispatch)
- **WHEN** the change is dispatched
- **THEN** input.md SHALL NOT contain a "Lessons from Prior Changes" section (own findings go via retry_context)

### Requirement: Findings are clustered and compact
The injected section SHALL be max 15 lines. Findings SHALL be clustered by keyword similarity (auth, XSS, rate-limit, etc.) and deduplicated. Each line shows the pattern and how many changes were affected.

#### Scenario: Multiple changes hit same pattern
- **GIVEN** 3 changes all had "no authentication" CRITICAL findings
- **WHEN** a new change is dispatched
- **THEN** the summary shows one clustered line: "No authentication on API routes (3 changes affected)"

### Requirement: Only CRITICAL and HIGH findings injected
The learnings section SHALL only include CRITICAL and HIGH severity findings. MEDIUM and LOW are noise at this stage.

#### Scenario: Mixed severity findings
- **GIVEN** findings include 2 CRITICAL, 3 HIGH, 5 MEDIUM
- **WHEN** injected into input.md
- **THEN** only the 2 CRITICAL and 3 HIGH appear in the summary
