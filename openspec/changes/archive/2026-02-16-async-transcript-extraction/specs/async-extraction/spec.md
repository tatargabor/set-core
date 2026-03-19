## ADDED Requirements

### Requirement: Background extraction
The transcript-based extraction (haiku LLM call + memory save) runs as a background process. The Stop hook exits immediately after forking it.

#### Scenario: Normal extraction
- **WHEN** Stop hook fires with a valid transcript_path and opsx skills detected
- **THEN** hook forks extraction to background, exits with code 0 in <1s, and extraction completes asynchronously

#### Scenario: No transcript or no skills
- **WHEN** Stop hook fires without transcript_path or no opsx skills in transcript
- **THEN** hook skips extraction entirely (same as current behavior), proceeds to Path 2

### Requirement: Lockfile concurrency control
Only one transcript extraction runs at a time per project. Uses `.set-core/.transcript-extraction.lock` with PID validation.

#### Scenario: No existing lock
- **WHEN** extraction starts and no lockfile exists
- **THEN** creates lockfile with current PID, runs extraction, removes lockfile on completion

#### Scenario: Active lock (another extraction running)
- **WHEN** extraction starts and lockfile exists with a living PID
- **THEN** skips extraction silently (the previous one is still working)

#### Scenario: Stale lock (crashed process)
- **WHEN** extraction starts and lockfile exists but PID is dead
- **THEN** removes stale lockfile, takes new lock, runs extraction

### Requirement: Cleanup
Background process cleans up its own temp files and lockfile on exit.

#### Scenario: Normal completion
- **WHEN** extraction finishes (success or no insights)
- **THEN** removes tmpfile and lockfile

#### Scenario: Process killed or error
- **WHEN** background process receives signal or encounters error
- **THEN** trap handler removes tmpfile and lockfile

### Requirement: Error logging
Background extraction logs errors to `.set-core/transcript-extraction.log` for debugging.

#### Scenario: Haiku call fails
- **WHEN** claude CLI returns empty or errors
- **THEN** logs error to log file, removes lock, exits cleanly
