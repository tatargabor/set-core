## MODIFIED Requirements

### Requirement: VR-REQ — Requirement review section builder
Read requirements[] and also_affects_reqs[] from change state. Look up titles from digest requirements.json. Build "Assigned Requirements" and "Cross-Cutting Requirements" sections. Append "Requirement Coverage Check" instruction block. Append "Overshoot Check" instruction block: instruct the reviewer to flag new routes, endpoints, components, or exports that do not correspond to any assigned requirement. Return empty string if no digest, no requirements, or empty requirements[].

#### Scenario: Review prompt includes overshoot instruction
- **WHEN** `build_req_review_section()` is called
- **AND** the change has assigned requirements (non-empty requirements[])
- **THEN** the returned section SHALL include an "Overshoot Check" instruction block
- **AND** the instruction SHALL tell the reviewer: "Flag any new route, endpoint, component, or export in the diff that does not correspond to an assigned requirement as [WARNING]: Potential overshoot"

#### Scenario: No requirements assigned skips overshoot instruction
- **WHEN** `build_req_review_section()` is called
- **AND** the change has no assigned requirements (empty requirements[] or no digest)
- **THEN** the returned section SHALL be empty
- **AND** no overshoot instruction SHALL be included

### Requirement: VR-REVIEW — LLM code review
Generate diff of change branch vs merge-base. Truncate diff to 30000 chars. Build review prompt via set-orch-core template review. Include overshoot detection instruction in review prompt. Run via run_claude with configurable model. On failure: escalate from configured model to opus, then skip. Return ReviewResult with has_critical flag. Detect CRITICAL via regex: `[CRITICAL]`, `severity.*critical`, `CRITICAL:`.

#### Scenario: Reviewer flags overshoot in diff
- **WHEN** the LLM code reviewer processes a diff
- **AND** the diff contains a new route, endpoint, or component not in the assigned requirements
- **THEN** the review output SHALL include a [WARNING] flag for the unmatched item

#### Scenario: Reviewer passes clean diff
- **WHEN** the LLM code reviewer processes a diff
- **AND** all new routes, endpoints, and components correspond to assigned requirements
- **THEN** no overshoot warnings SHALL appear in the review output
