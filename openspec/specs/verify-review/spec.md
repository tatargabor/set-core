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

#### VR-AC — Acceptance criteria in review prompt
- When requirements have `acceptance_criteria`, render as `- [ ] <item>` checkboxes under each REQ
- When AC absent, fall back to `- REQ-ID: title — brief` (existing behavior)
- AC-aware coverage check: per-AC-item `ISSUE: [CRITICAL] REQ-ID: "<ac item>" not implemented`
- Coarse-grained check retained as fallback when no AC items present
- Cross-cutting requirements: title-only, no AC items (unchanged)

#### VR-IKP — IKP testing context in the review prompt
- When the change has non-empty `ikp_packs` and `has_ikp_pipeline()` is true, the review prompt includes an IKP testing section: sandbox setup, recommended mock strategies, and edge cases to check (L4 context, `_build_ikp_review_context` in `verifier.py`)
- With no `ikp_packs`, the review prompt is unchanged
- Added from change `ikp-decomposer-dispatch` by hand on archive (2026-10-20): this spec predates the requirement/scenario format, so its delta could not be merged mechanically
