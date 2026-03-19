## ADDED Requirements

### Requirement: Hook Fix Test Script
A test script (`benchmark/tests/test-hooks.sh`) SHALL validate all memory hook fixes in isolation using a temporary shodh-memory storage directory. The script MUST NOT modify production memory storage.

#### Scenario: Auto-ingest disabled
- **WHEN** the test runs `set-memory proactive "test context"` with the temp storage
- **THEN** zero memories with `experience_type: Conversation` SHALL exist in temp storage

#### Scenario: Change tag propagation
- **WHEN** the test simulates transcript extraction with change name "test-change"
- **THEN** the saved memory SHALL have a `change:test-change` tag

#### Scenario: Code-map generation
- **WHEN** the test creates fake commits in a temp repo and triggers the save hook
- **THEN** a code-map memory SHALL exist with `code-map` tag

#### Scenario: Convention extraction prompt
- **WHEN** the test inspects the save hook source
- **THEN** the LLM prompt SHALL contain a convention extraction section

### Requirement: Pre-flight Infrastructure Check
A pre-flight script (`benchmark/preflight.sh`) SHALL validate benchmark infrastructure before a run. It MUST exit non-zero if any check fails.

#### Scenario: All checks pass
- **WHEN** hooks are installed, memory is healthy, all 12 change files and test scripts exist, glob patterns work, and ports are free
- **THEN** the script SHALL exit 0 with a summary of passed checks

#### Scenario: Missing hook
- **WHEN** `.claude/settings.json` does not contain `wt-hook-memory-save`
- **THEN** the script SHALL exit 1 with an error identifying the missing hook

#### Scenario: Glob pattern regression
- **WHEN** the glob `[0-9]*.md` does not match exactly 12 files in `benchmark/changes/`
- **THEN** the script SHALL exit 1 with the count mismatch

### Requirement: Single-Change Smoke Test
The hook test script SHALL support a `--smoke` mode that runs one change (C01 product-catalog) end-to-end with memory enabled, then validates memory quality.

#### Scenario: Smoke test passes
- **WHEN** C01 completes with memory enabled
- **THEN** the script SHALL verify: at least 1 memory with `change:product-catalog` tag, zero `Conversation` type memories from proactive-context, code-map memory exists, `set-memory stats` noise rate below 20%

#### Scenario: Smoke test fails on noise
- **WHEN** C01 completes but proactive-context creates `Conversation` memories
- **THEN** the script SHALL exit 1 with "auto_ingest noise detected"
