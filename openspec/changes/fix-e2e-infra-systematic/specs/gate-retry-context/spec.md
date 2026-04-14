## ADDED Requirements

### Requirement: Verdict stores structured findings

Gate verdict sidecars (`<session_id>.verdict.json`) SHALL persist a `findings` array alongside the existing `summary` field when the gate produces structured findings (reviewer FILE/LINE/FIX blocks, spec_verify CRITICAL items, Playwright failing tests, TypeScript errors). Each finding SHALL include `id`, `severity`, `title`, `file`, `line_start`, `line_end`, `code_context`, `fix_block`, `fingerprint`, and `confidence` fields. Legacy verdicts without `findings` SHALL remain parseable (backward compatibility).

`fingerprint` SHALL be computed as the first 8 hex chars of SHA-256 of `f"{file}:{line_start}:{title[:50]}"` — stable across retries for the same finding.

#### Scenario: Review gate produces structured findings
- **GIVEN** a review gate run where the reviewer output contains a CRITICAL block with FILE, LINE, FIX
- **WHEN** the gate writes its verdict sidecar
- **THEN** `findings` SHALL contain one entry per reviewer block
- **AND** each entry SHALL populate `file`, `line_start`, `fix_block` from the parsed output
- **AND** `fingerprint` SHALL be an 8-char hex string

#### Scenario: spec_verify produces structured findings
- **GIVEN** a spec_verify run with `CRITICAL_COUNT: 2` and two structured CRITICAL blocks in the output
- **WHEN** the verdict is persisted
- **THEN** `findings` SHALL have length 2
- **AND** `summary` SHALL contain the `VERIFY_RESULT: FAIL with CRITICAL_COUNT: 2` text

#### Scenario: Legacy verdict without findings
- **GIVEN** a verdict.json file written before this change (no `findings` field)
- **WHEN** the engine loads the verdict
- **THEN** parsing SHALL succeed
- **AND** the in-memory representation SHALL have `findings=[]` and fall back to `summary`-only retry context

### Requirement: Structured finding extractors

The framework SHALL provide per-gate finding extractors in `lib/set_orch/findings.py`:

- `extract_build_findings(output)` — TypeScript/lint errors with file, line, error message.
- `extract_test_findings(output)` — vitest/jest failure assertions with test name, file, error.
- `extract_e2e_findings(output)` — Playwright failing test names with test file, line, failure message.
- `extract_review_findings(output)` — reviewer CRITICAL/HIGH blocks with file, line, fix snippet.
- `extract_spec_verify_findings(output)` — spec_verify CRITICAL blocks.

Each extractor returns `list[Finding]` (typed dataclass). Extractors SHALL be robust against partial output (return what's parseable, log on unparseable regions).

#### Scenario: Extractor parses Playwright failure
- **GIVEN** Playwright output: `1) tests/e2e/cart.spec.ts:145:3 › cart total › expected 5, got 3`
- **WHEN** `extract_e2e_findings(output)` runs
- **THEN** the returned list SHALL contain a finding with `file="tests/e2e/cart.spec.ts"`, `line_start=145`, `title="cart total › expected 5, got 3"`

#### Scenario: Extractor handles empty output gracefully
- **GIVEN** an empty gate output
- **WHEN** any extractor runs
- **THEN** it SHALL return `[]` without raising

### Requirement: Layer 1 in-gate quick fix

When a gate in `{build, test, rules}` fails AND the agent's session is younger than 60 minutes AND the gate's `in_gate_attempts < budget`, the engine SHALL invoke `claude --resume <session_id>` with a targeted fix prompt rendered from the structured findings. The prompt SHALL scope the allowed file changes and expect a "done" or "blocked" reply. After the agent replies, ONLY the failing gate SHALL re-run.

#### Scenario: build fail, fresh session, budget available
- **GIVEN** `build` fails with 3 TypeScript errors in `src/cart.ts`
- **AND** the agent's session started 15 minutes ago
- **AND** `gate_retries.build.in_gate_attempts = 0`
- **WHEN** Layer 1 triggers
- **THEN** `claude --resume <sid>` SHALL be invoked with a prompt listing the 3 errors and their file/line
- **AND** the prompt SHALL include: "Touch ONLY files: src/cart.ts (plus required imports). Reply 'done' when fixed and committed."
- **AND** after the agent replies, `build` SHALL re-run
- **AND** `build`'s downstream gates SHALL NOT re-run (isolated re-check)

#### Scenario: Session too old
- **GIVEN** the agent's session started 90 minutes ago (> 60 min)
- **WHEN** any gate fails
- **THEN** Layer 1 SHALL be skipped
- **AND** execution SHALL proceed directly to Layer 2

#### Scenario: Gate not in Layer 1 eligible set
- **GIVEN** `review` fails (review not in `{build, test, rules}`)
- **WHEN** the failure is handled
- **THEN** Layer 1 SHALL be skipped
- **AND** Layer 2 SHALL run

### Requirement: Layer 2 targeted subagent

When Layer 1 is skipped or exhausted AND `subagent_attempts < budget`, the engine SHALL spawn a fresh Claude session as a dedicated fix-subagent. The subagent SHALL use model `sonnet`, `--max-turns 15`, a 300s wall timeout, and a gate-specific prompt template. After the subagent exits, the engine SHALL validate the `git diff` against a per-gate allowlist; scope violations SHALL trigger `git reset --hard` and mark the attempt blocked.

Gate-specific templates SHALL live in `templates/core/rules/fix-subagent/<gate>.md`.

#### Scenario: spec_verify fail → subagent applies findings
- **GIVEN** `spec_verify` fails with 2 CRITICAL findings (each with file, line, fix_block)
- **WHEN** Layer 2 triggers
- **THEN** a fresh Claude session SHALL be spawned with the spec_verify fix-subagent template
- **AND** the prompt SHALL embed both findings verbatim including their fix_block snippets
- **AND** the subagent SHALL commit fixes to the worktree
- **AND** on return, the engine SHALL re-run `spec_verify` plus any upstream gates invalidated by the diff

#### Scenario: Subagent violates scope
- **GIVEN** the fix-subagent template allowlist is `src/cart.ts, tests/e2e/cart.spec.ts`
- **AND** after execution, `git diff` shows changes in `openspec/changes/<name>/proposal.md`
- **WHEN** the engine validates the diff
- **THEN** `git reset --hard <baseline_sha>` SHALL revert the worktree
- **AND** the SubagentResult SHALL report `outcome="scope_violation"`
- **AND** execution SHALL escalate to Layer 3

#### Scenario: Subagent times out
- **GIVEN** the subagent does not return within 300 seconds
- **WHEN** the engine's subprocess timeout fires
- **THEN** the subagent process SHALL be killed
- **AND** any uncommitted changes SHALL be left as-is (agent may have committed partial progress)
- **AND** the attempt counts as one Layer 2 attempt (budget consumed)

### Requirement: Layer 3 consolidated redispatch

When Layers 1–2 are exhausted or convergence detection fires, the engine SHALL reset the change to `verify-failed` status and build a consolidated `retry_context` containing findings from all gate attempts across all prior Layer 1–2 executions, plus convergence warnings for fingerprints exceeding threshold, plus prior commits summary. Layer 3 SHALL consume at most 1 per change when `smart_retry.enabled=true` (reduced from the current default of 2–3).

#### Scenario: Consolidated retry_context assembly
- **GIVEN** a change has prior findings: spec_verify (3 CRITICAL across 2 attempts), review (2 CRITICAL, 1 attempt), build (5 TS errors, 2 Layer 1 attempts)
- **WHEN** Layer 3 retry_context is built
- **THEN** the retry_context markdown SHALL contain sections for each gate listing structured findings with file/line/fix_block
- **AND** it SHALL include "Convergence failures" listing fingerprints with count >= 3
- **AND** it SHALL include "Prior commits" with `git log --oneline main..HEAD` (capped at 30)

#### Scenario: Reduced redispatch budget
- **GIVEN** `smart_retry.enabled=true` and default config
- **WHEN** the engine evaluates the Layer 3 budget
- **THEN** `max_redispatch_per_change` SHALL be 1 (not the legacy 2–3)

### Requirement: Convergence detection

On every gate result with findings, the engine SHALL update `change.extras.finding_fingerprints[fp].count` and `last_seen`. If any fingerprint's `count >= 3`, the engine SHALL emit `RETRY_CONVERGENCE_FAIL` and trigger Layer 3 immediately (bypassing remaining Layer 1–2 budget).

The threshold SHALL be configurable via `orchestration.smart_retry.convergence.same_finding_threshold` (default 3).

#### Scenario: Third occurrence of same finding
- **GIVEN** `change.extras.finding_fingerprints = {"a3f92c7e": {"count": 2, ...}}`
- **WHEN** a new gate result contains a finding with fingerprint `a3f92c7e`
- **THEN** the count SHALL update to 3
- **AND** `RETRY_CONVERGENCE_FAIL` SHALL be emitted with `{change, fingerprints: [{fp: "a3f92c7e", count: 3, title: ...}]}`
- **AND** Layer 3 SHALL trigger even if per-gate Layer 2 budget remains

#### Scenario: Distinct findings don't converge
- **GIVEN** five different fingerprints each appearing once
- **WHEN** the pipeline runs
- **THEN** no convergence SHALL fire
- **AND** each fingerprint's count SHALL be 1 in state

#### Scenario: Threshold configurable
- **GIVEN** `orchestration.smart_retry.convergence.same_finding_threshold: 2`
- **WHEN** a fingerprint reaches count=2
- **THEN** convergence SHALL fire immediately (threshold lowered for this project)

### Requirement: RESUME_CONTEXT.md for resumed changes

On `MANUAL_RESUME` or `ISSUE_DIAGNOSED_TIMEOUT` recovery paths, the engine SHALL write a `RESUME_CONTEXT.md` file into the change's worktree containing (a) why the change is being resumed, (b) prior gate findings not yet resolved, (c) convergence warnings for tracked fingerprints, (d) prior commits summary. The dispatcher's resume prompt SHALL reference this file.

#### Scenario: Resume after phase timeout
- **GIVEN** a change was killed via `max_phase_runtime_secs` timeout at attempt 4
- **AND** prior spec_verify attempts produced 2 unresolved CRITICAL findings
- **WHEN** the engine resumes the change
- **THEN** `<wt>/RESUME_CONTEXT.md` SHALL exist
- **AND** it SHALL contain "Prior gate findings (to address on resume)" section listing both CRITICAL findings with file/line/fix_block
- **AND** the resume prompt SHALL include: "Read RESUME_CONTEXT.md first."

#### Scenario: Manual resume
- **WHEN** a user triggers `MANUAL_RESUME` for a change
- **THEN** `RESUME_CONTEXT.md` SHALL be written before the agent is dispatched
- **AND** the file SHALL include "Why you're resuming: manually requested by user"
