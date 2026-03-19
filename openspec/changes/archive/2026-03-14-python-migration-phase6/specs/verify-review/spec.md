## verify-review

LLM code review with model escalation and requirement-aware prompting.

### Requirements

#### VR-REQ — Requirement review section builder
- Read requirements[] and also_affects_reqs[] from change state
- Look up titles from digest requirements.json
- Build "Assigned Requirements" and "Cross-Cutting Requirements" sections
- Append "Requirement Coverage Check" instruction block
- Return empty string if no digest, no requirements, or empty requirements[]

#### VR-REVIEW — LLM code review
- Generate diff of change branch vs merge-base (origin/HEAD or main)
- Truncate diff to 30000 chars
- Build review prompt via set-orch-core template review
- Run via run_claude with configurable model
- On failure: escalate from configured model to opus, then skip
- Return `ReviewResult` with has_critical flag
- Detect CRITICAL via regex: `[CRITICAL]`, `severity.*critical`, `CRITICAL:`

#### VR-DESIGN — Design compliance section
- Build design compliance section from design-snapshot.md if available
- Integrated into review prompt alongside requirement section
