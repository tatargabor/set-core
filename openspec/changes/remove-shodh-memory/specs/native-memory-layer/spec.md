## IN SCOPE
- The framework's memory layer is the native Claude Code per-repository Markdown directory
- What loads at session start, and the size limit that governs it
- What the framework may and may not write into that directory
- The confidentiality rule that outlives the removed subsystem
- An explicit, testable statement of the capabilities deliberately NOT replaced

## OUT OF SCOPE
- Adopting any third-party memory system as a replacement
- Restoring semantic search, tags, temporal queries or automatic extraction on another substrate
- The GTD todo system, which was backed by the removed subsystem and is not ported
- Deleting the archived store of the removed subsystem

## ADDED Requirements

### Requirement: The framework ships no memory subsystem of its own
set-core SHALL NOT provide, install, or depend on a memory store, memory daemon, memory CLI,
or memory hook. The memory layer available to a session is the one the runtime provides, and
the framework SHALL treat it as read-mostly context rather than as a system it operates.

#### Scenario: No memory command is installed
- **WHEN** the framework's `bin/` directory is enumerated after installation
- **THEN** it SHALL contain no executable whose name begins with `set-memory` or `set-hook-memory`

#### Scenario: No memory hook is deployed
- **WHEN** `set-deploy-hooks` writes or updates any project's `.claude/settings.json`
- **THEN** the resulting file SHALL contain zero hook commands beginning with `set-hook-memory`

#### Scenario: No memory package is imported
- **WHEN** every Python module under `lib/` and every script under `bin/` is scanned for imports
- **THEN** none SHALL import `shodh_memory`, `set_memoryd`, or `set_hooks`

### Requirement: The native memory directory is the memory layer
The framework SHALL document the runtime's per-repository memory directory as the single
place durable cross-session knowledge lives, and SHALL NOT introduce a second store beside
it.

#### Scenario: The rule book names the real mechanism
- **WHEN** a session reads the project instruction file's memory section
- **THEN** it SHALL describe the native per-repository Markdown directory and its index file
- **AND** it SHALL NOT instruct the session to look for an injected block that no component emits

#### Scenario: A second store is not introduced
- **WHEN** the framework needs to persist knowledge that must survive a session
- **THEN** it SHALL write a Markdown file into the native memory directory, or nothing

### Requirement: The index size limit is stated, because it silently truncates
Only the first 200 lines, or 25 KB, of the memory index load at session start. The framework
SHALL state this limit wherever it instructs anyone to maintain that index, because content
beyond the cut is not injected and its absence produces no warning.

#### Scenario: The limit is documented where the index is described
- **WHEN** framework documentation or rules describe maintaining the memory index
- **THEN** the 200-line / 25 KB startup limit SHALL be stated alongside

#### Scenario: An index approaching the limit is a known condition
- **WHEN** a memory index exceeds 150 lines or 20 KB
- **THEN** the framework SHALL treat that as a condition to report, not as normal
- **AND** the report SHALL say that content past the cut loads for nobody

### Requirement: Confidentiality survives the removal
The boundary the removed subsystem breached SHALL continue to bind whatever writes memory.
No memory file may contain a consumer project's name, a person's name, or content derived
from a consumer's data.

#### Scenario: A memory naming a consumer entity is a defect
- **WHEN** a memory file contains a consumer project name, a partner name, or a personal name
- **THEN** it SHALL be treated as a defect to correct, not as harmless content

#### Scenario: Harness artifacts are never memory
- **WHEN** a task notification, a cross-session message, another agent's prompt, or a meeting
  transcript fragment is available to whatever writes memory
- **THEN** it SHALL NOT be stored verbatim as a memory

### Requirement: A memory records a fact, never a claim about the user's state
Whatever writes memory SHALL record what was learned. It SHALL NOT record an inferred
emotional state, and SHALL NOT label a memory with a sentiment the source text does not
support.

#### Scenario: Enthusiasm is not stored as frustration
- **WHEN** a prompt contains emphasis such as repeated exclamation marks
- **THEN** no memory SHALL be written asserting that the user is frustrated

#### Scenario: No sentiment label is injected into a later session
- **WHEN** a session begins or a prompt is submitted
- **THEN** no component SHALL inject a statement about the user's emotional state

### Requirement: The capabilities not replaced are stated, not discovered
Removing the subsystem removes real capabilities. The framework SHALL record which ones are
gone, so a later session reaches for a documented absence rather than a missing feature.

#### Scenario: The losses are enumerated
- **WHEN** framework documentation describes the memory layer
- **THEN** it SHALL state that semantic search, tag filtering, temporal queries, full-text
  search, cross-device sync, version history and automatic session-end extraction are not
  available
- **AND** it SHALL record that the removed subsystem provided all of them and still produced
  one reusable line in 187 injections over 21 days

#### Scenario: A request for a removed capability has an answer
- **WHEN** a session needs to search memory by concept, tag, or date range
- **THEN** the documented answer SHALL be to read the index and open the topic files, not to
  reinstall a store
