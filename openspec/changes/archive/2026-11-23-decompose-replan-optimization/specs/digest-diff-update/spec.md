## ADDED Requirements

<!--
IN SCOPE:
- Per-section content-hashed digest with reuse on unchanged sections.
- Deterministic Python reducer that merges per-section outputs into `requirements.json`, `coverage.json`, `triage.md`.
- Section identification rules (set-spec-capture segmentation when available; markdown heading fallback).
- On-disk layout `set/orchestration/digest/sections/<section-id>.json`.
- Backward compatibility: existing digest output paths remain unchanged.

OUT OF SCOPE:
- LLM-based merging of section outputs (the reducer is Python only).
- Cross-document section dedup.
- Spec authoring tooling (we consume what set-spec-capture or markdown produces).
-->

### Requirement: Section identification
The system SHALL identify spec sections in this priority order: (1) `set-spec-capture` segmentation when its output is available; (2) top-level markdown headings (`#`, `##`) with stable kebab-case ids derived from heading text; (3) the entire file as a single section when neither is available.

#### Scenario: set-spec-capture segmentation used
- **WHEN** the spec was produced by `set-spec-capture` and section ids are present in its output metadata
- **THEN** the digest SHALL use those section ids as the section identifiers

#### Scenario: Markdown heading fallback
- **WHEN** no set-spec-capture metadata is present and the spec contains markdown headings
- **THEN** each `##` heading SHALL define a section
- **AND** the section id SHALL be the heading text lowercased, non-alphanumeric replaced with `-`, deduplicated by suffix `-2`, `-3`, etc.

#### Scenario: Single-section fallback
- **WHEN** the spec has neither set-spec-capture metadata nor markdown headings
- **THEN** the entire file SHALL be treated as one section with id `<filename-stem>`

### Requirement: Section content hashing
For each section, the system SHALL compute a `sha256` over the section's normalized text (trailing whitespace stripped, newlines normalized to `\n`) and store it in the per-section output file.

#### Scenario: Hash stored with section output
- **WHEN** a section is digested for the first time
- **THEN** `digest/sections/<section-id>.json` SHALL contain `{"section_id": "...", "content_hash": "<sha256>", "requirements": [...], "ambiguities": [...], "coverage_hints": [...], "gaps": [...]}`

#### Scenario: Hash matches → reuse
- **WHEN** the digest runs and an existing `digest/sections/<section-id>.json` matches the recomputed `content_hash`
- **THEN** the system SHALL reuse the existing section output without invoking Claude
- **AND** SHALL log at INFO level: `digest section <id> reused (hash match)`

#### Scenario: Hash differs → recompute
- **WHEN** the digest runs and an existing section file's `content_hash` does not match the recomputed hash
- **THEN** the system SHALL invoke a per-section Claude call (model: configurable, default Sonnet)
- **AND** SHALL overwrite the section file with the new output

### Requirement: Deterministic Python reducer
After per-section outputs are produced, the system SHALL run a deterministic Python reducer (no LLM call) that merges them into `requirements.json`, `coverage.json`, and `triage.md`. The reducer SHALL produce byte-identical output for byte-identical section inputs.

#### Scenario: Reducer is deterministic
- **WHEN** the reducer is invoked twice on the same set of section files
- **THEN** the output bytes of `requirements.json`, `coverage.json`, and `triage.md` SHALL be identical between the two runs

#### Scenario: Gaps are unioned, not overwritten
- **WHEN** two sections each report a gap for the same requirement id with different `reason` strings
- **THEN** the reducer SHALL emit both gap entries in `triage.md`, deduplicated by `(requirement_id, reason)` pair

#### Scenario: Reducer fails on schema violation
- **WHEN** a section file is missing a required field (e.g., `content_hash`)
- **THEN** the reducer SHALL fail with a descriptive error naming the section and the missing field
- **AND** SHALL NOT produce partial output files

### Requirement: Backward-compatible output paths
The system SHALL continue to write `requirements.json`, `coverage.json`, `triage.md`, and `domains/<name>.md` at their existing paths under `set/orchestration/digest/`. The new per-section files SHALL live under `set/orchestration/digest/sections/`.

#### Scenario: Existing consumers unaffected
- **WHEN** the planner reads `set/orchestration/digest/requirements.json`
- **THEN** it SHALL find the file at the same path with the same JSON shape as before this change

### Requirement: Spec edit triggers selective re-digest
On a digest run after a spec edit, only sections whose content hash changed SHALL be re-invoked against Claude. Unchanged sections SHALL be reused from disk.

#### Scenario: Single-section edit
- **WHEN** the spec is edited in section `auth` only and re-digest is invoked
- **THEN** only the `auth` section SHALL trigger a per-section Claude call
- **AND** all other sections SHALL be reused
- **AND** the reducer SHALL re-merge all sections to produce updated `requirements.json` etc.

### Requirement: Section storage co-located with digest cache
The per-section files SHALL live under the project's digest output directory (`set/orchestration/digest/sections/`), not under the global `~/.cache/set-orch/digest-cache/`. The global cache directory MAY continue to serve full-prompt content-addressed lookups for backward compatibility but SHALL NOT be the source of truth for per-section storage.

#### Scenario: Sections stored per-project
- **WHEN** two projects digest specs with the same content
- **THEN** each project SHALL have its own `set/orchestration/digest/sections/` directory
- **AND** the section files SHALL NOT be shared via the global cache directory
