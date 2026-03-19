## ADDED Requirements

### Requirement: Proactive context command
The `set-memory proactive` command SHALL call shodh-memory's `proactive_context()` Python API with the provided conversation context. It SHALL return memories with `relevance_score` and `relevance_reason` fields as JSON to stdout. If shodh-memory is not available, it SHALL output `[]` and exit 0.

#### Scenario: Proactive recall with context
- **WHEN** `set-memory proactive "user is working on shopping-cart feature with Prisma ORM"` is run
- **AND** shodh-memory contains relevant memories
- **THEN** the command outputs a JSON array where each entry includes `relevance_score` (float) and `relevance_reason` (string) alongside the memory content

#### Scenario: Proactive recall with limit
- **WHEN** `set-memory proactive "context text" --limit 3` is run
- **THEN** at most 3 memories are returned, ordered by relevance_score descending

#### Scenario: Proactive recall without shodh-memory
- **WHEN** `set-memory proactive "context text"` is run and shodh-memory is not available
- **THEN** the command outputs `[]` and exits 0

#### Scenario: Proactive recall with empty context
- **WHEN** `set-memory proactive ""` is run (empty context string)
- **THEN** the command outputs `[]` and exits 0

### Requirement: Proactive output includes relevance metadata
Each memory returned by `set-memory proactive` SHALL include `relevance_score` (0.0–1.0 float) and `relevance_reason` (human-readable string) as top-level fields in the JSON output. These fields come directly from the `proactive_context()` API response.

#### Scenario: Output format with relevance fields
- **WHEN** proactive recall returns memories
- **THEN** each memory object in the JSON array contains at minimum: `content`, `relevance_score`, `relevance_reason`, `experience_type`, `tags`

### Requirement: Graceful degradation for proactive_context API
If the `proactive_context()` method is not available in the installed shodh-memory version, the command SHALL fall back to `recall()` with mode=hybrid and log a warning to the log file. Output format SHALL remain consistent (relevance_score set to "N/A", relevance_reason omitted).

#### Scenario: Old shodh-memory version without proactive_context
- **WHEN** `set-memory proactive "context"` is run
- **AND** the installed shodh-memory does not have `proactive_context()` method
- **THEN** the command falls back to `recall()` with mode=hybrid and returns results with `relevance_score` set to `"N/A"`
