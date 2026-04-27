## ADDED Requirements

### Requirement: Verdict stores structured findings

Gate verdict sidecars (`<session_id>.verdict.json`) SHALL optionally persist a `findings` array alongside the existing `summary` field when the gate produces structured findings (reviewer FILE/LINE/FIX blocks, spec_verify CRITICAL items, Playwright failing tests). Each finding SHALL include `id`, `severity`, `title`, `file`, `line_start`, `line_end`, `code_context`, `fix_block`, `fingerprint`, and `confidence` fields. Legacy verdicts without `findings` SHALL remain parseable (backward compatibility).

`fingerprint` SHALL be computed as the first 8 hex chars of `SHA-256(f"{file}:{line_start}:{title[:50]}")` — stable across retries for the same finding.

Retry-context assembly SHALL prefer `findings` when present, rendering a structured FILE/LINE/FIX block per finding in the next iteration's retry prompt. When `findings` is absent or empty, retry-context SHALL fall back to the existing `summary`-only rendering.

#### Scenario: Review gate produces structured findings
- **GIVEN** a review gate run where the reviewer output contains CRITICAL blocks with FILE, LINE, FIX fields
- **WHEN** the gate writes its verdict sidecar
- **THEN** `findings` SHALL contain one entry per reviewer block
- **AND** each entry SHALL populate `file`, `line_start`, `fix_block` from the parsed output
- **AND** `fingerprint` SHALL be an 8-char hex string

#### Scenario: spec_verify produces structured findings
- **GIVEN** a spec_verify run with `CRITICAL_COUNT: 2` and two structured CRITICAL blocks in the output
- **WHEN** the verdict is persisted
- **THEN** `findings` SHALL have length 2
- **AND** `summary` SHALL contain the `VERIFY_RESULT: FAIL with CRITICAL_COUNT: 2` text

#### Scenario: E2E gate produces structured findings
- **GIVEN** a Playwright run where 2 tests failed
- **WHEN** the gate writes its verdict sidecar
- **THEN** `findings` SHALL contain one entry per failing test
- **AND** each `file` SHALL be the spec path and `line_start` SHALL be the failing line when parseable

#### Scenario: Legacy verdict without findings
- **GIVEN** a verdict.json file written before this change (no `findings` field)
- **WHEN** the engine loads the verdict
- **THEN** parsing SHALL succeed
- **AND** the in-memory representation SHALL have `findings=[]`
- **AND** retry context generation SHALL fall back to the `summary`-only rendering path

#### Scenario: Retry-context uses findings when present
- **GIVEN** a review gate verdict with 2 findings (each with file, line, fix_block)
- **WHEN** the engine builds the redispatch retry_context
- **THEN** the retry_context SHALL contain a "Review findings" section
- **AND** each finding SHALL be rendered as a block containing FILE, LINE, and the verbatim fix_block
- **AND** the 1-line summary SHALL also appear at the top of the section as context

#### Scenario: Extractor returns empty list gracefully
- **GIVEN** a gate output that the extractor cannot parse into any finding
- **WHEN** the extractor runs
- **THEN** it SHALL return `[]` without raising
- **AND** a WARNING SHALL be logged noting the unparseable region
- **AND** verdict.json SHALL omit the `findings` field (or write `findings: []`)
- **AND** retry-context SHALL fall back to `summary`
