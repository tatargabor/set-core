## ADDED Requirements

### Requirement: Staging file write instead of direct memory save

PATH 1 transcript extraction SHALL write Haiku output to a staging file at `.set-core/.staged-extract-{transcript-basename}` instead of calling `set-memory remember` directly. Each extraction MUST overwrite (not append to) the staging file for the same transcript.

The staging file format SHALL be identical to the current Haiku output: one line per insight in `Type|tags|content` format. Lines that are empty, "NONE", or malformed SHALL still be written to the file (filtering happens at commit time).

#### Scenario: First extraction creates staging file
- **WHEN** the hook runs PATH 1 extraction for transcript `abc123.jsonl`
- **AND** no staged file exists for `abc123`
- **THEN** the hook writes Haiku output to `.set-core/.staged-extract-abc123`
- **AND** `set-memory remember` is NOT called

#### Scenario: Subsequent extraction overwrites staging file
- **WHEN** the hook runs PATH 1 extraction for transcript `abc123.jsonl`
- **AND** a staged file already exists for `abc123` with content from a previous extraction
- **THEN** the hook overwrites `.set-core/.staged-extract-abc123` with the new Haiku output
- **AND** the previous content is completely replaced
- **AND** `set-memory remember` is NOT called

#### Scenario: Atomic write prevents corruption
- **WHEN** the hook writes a staging file
- **THEN** it SHALL write to a temporary file first, then atomically move it to the final path using `mv`

### Requirement: Commit staged extractions on session switch

Before running PATH 1 extraction, the hook SHALL check for staged files from **different** transcripts than the current one. For each such staged file, the hook SHALL parse and commit its contents to `set-memory`, then delete the staged file and its timestamp file.

Commit parsing SHALL follow the same `Type|tags|content` format parsing already in the hook (validate type, cap at 5 insights + 2 conventions, skip empty/NONE/malformed lines).

#### Scenario: Commit on session switch
- **WHEN** the hook fires for transcript `session-2.jsonl`
- **AND** `.set-core/.staged-extract-session-1` exists with valid insights
- **THEN** the hook commits `session-1`'s insights to `set-memory remember`
- **AND** deletes `.set-core/.staged-extract-session-1`
- **AND** deletes `.set-core/.staged-extract-session-1.ts` (if exists)
- **AND** then proceeds with extraction for `session-2`

#### Scenario: Multiple staged files from different sessions
- **WHEN** the hook fires for transcript `session-3.jsonl`
- **AND** staged files exist for both `session-1` and `session-2`
- **THEN** both staged files are committed to `set-memory`
- **AND** both staged files and their timestamp files are deleted

#### Scenario: No commit for current transcript's staged file
- **WHEN** the hook fires for transcript `session-1.jsonl`
- **AND** `.set-core/.staged-extract-session-1` exists
- **THEN** the hook does NOT commit `session-1`'s staged file (it will be overwritten)

### Requirement: Stale staged file auto-commit

Staged files older than 1 hour SHALL be committed regardless of which transcript is current. Age is determined from the `.ts` (timestamp) file, or from the staged file's modification time if no `.ts` file exists.

#### Scenario: Stale file from same session committed
- **WHEN** the hook fires for transcript `session-1.jsonl`
- **AND** `.set-core/.staged-extract-session-1` exists
- **AND** `.set-core/.staged-extract-session-1.ts` contains a timestamp older than 1 hour
- **THEN** the hook commits `session-1`'s insights to `set-memory`
- **AND** deletes both the staged file and timestamp file
- **AND** then proceeds with fresh extraction for `session-1`

#### Scenario: Stale file without timestamp file
- **WHEN** a staged file exists but its `.ts` file is missing
- **AND** the staged file's filesystem modification time is older than 1 hour
- **THEN** the hook commits and deletes the staged file

### Requirement: Debounce extraction via timestamp

Before calling Haiku LLM, the hook SHALL check `.set-core/.staged-extract-{id}.ts` for the last extraction timestamp. If less than 5 minutes have elapsed, the hook SHALL skip the Haiku call entirely and return early (leaving the existing staged file untouched).

After a successful Haiku extraction, the hook SHALL write the current epoch seconds to the `.ts` file.

#### Scenario: Extraction skipped within debounce window
- **WHEN** the hook fires for transcript `session-1.jsonl`
- **AND** `.set-core/.staged-extract-session-1.ts` exists with timestamp 2 minutes ago
- **THEN** the hook does NOT call Haiku LLM
- **AND** the existing `.staged-extract-session-1` file is untouched
- **AND** the log file records the skip

#### Scenario: Extraction proceeds after debounce expires
- **WHEN** the hook fires for transcript `session-1.jsonl`
- **AND** `.set-core/.staged-extract-session-1.ts` exists with timestamp 6 minutes ago
- **THEN** the hook calls Haiku LLM for extraction
- **AND** overwrites `.staged-extract-session-1` with new output
- **AND** updates `.staged-extract-session-1.ts` with current time

#### Scenario: First extraction for a transcript (no timestamp file)
- **WHEN** the hook fires for transcript `session-1.jsonl`
- **AND** no `.staged-extract-session-1.ts` file exists
- **THEN** the hook calls Haiku LLM for extraction
- **AND** creates both `.staged-extract-session-1` and `.staged-extract-session-1.ts`

### Requirement: Integration tests cover all staging scenarios

A test script `tests/test_save_hook_staging.sh` SHALL verify the staging behavior using mocked externals (`set-memory`, `claude` CLI). The test MUST cover:
1. First extraction creates staged file (no direct memory save)
2. Second extraction overwrites staged file
3. Session switch commits old staged file to memory
4. Debounce skips extraction within 5-minute window
5. Stale file (>1 hour) auto-committed even for same session
6. No-opsx-skill transcript skips extraction entirely (existing behavior preserved)
7. PATH 2 (commit-based) continues to work independently

#### Scenario: Tests pass with mocked externals
- **WHEN** `bash tests/test_save_hook_staging.sh` is run
- **AND** `set-memory` and `claude` CLI are mocked via PATH override
- **THEN** all test cases pass
- **AND** no real API calls or memory mutations occur

#### Scenario: Existing PATH 2 behavior preserved
- **WHEN** the hook runs with new commits (PATH 2 trigger)
- **THEN** design choice extraction continues to work as before
- **AND** staging logic does not interfere with commit-based extraction
