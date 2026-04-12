## ADDED Requirements

### Requirement: Archive-before-overwrite helper
The system SHALL provide a reusable helper `archive_and_write(path, content, *, reason=None, max_archives=None)` in `lib/set_orch/archive.py` that snapshots an existing file before writing new content.

#### Scenario: Write to existing file
- **WHEN** `archive_and_write()` is called with a path that already exists
- **THEN** the current contents of the file are copied to `<orchestration_dir>/archives/<relative-path>/<timestamp>.<ext>`
- **THEN** the new content is written atomically to the original path (via tempfile + rename)
- **THEN** the archive file preserves the original mtime and mode (via `shutil.copy2`)

#### Scenario: Write to new file
- **WHEN** `archive_and_write()` is called with a path that does not yet exist
- **THEN** no archive is created
- **THEN** the new content is written atomically to the path

#### Scenario: Atomic write semantics
- **WHEN** content is written via `archive_and_write()`
- **THEN** the write uses a temp-file + rename pattern so that readers never observe a partial file
- **THEN** if the write is interrupted, the original file remains untouched (because the archive was taken first)

### Requirement: Archive metadata sidecar
The system SHALL write a `.meta.json` sidecar next to the archived snapshot when a reason is provided.

#### Scenario: Reason supplied
- **WHEN** `archive_and_write()` is called with a non-null `reason` argument
- **THEN** a sidecar file `<archive>.meta.json` is written next to the snapshot containing `reason`, `ts`, and optionally `commit` (resolved via `git rev-parse HEAD` in the archive's working directory if available)
- **THEN** sidecar write failures are logged at WARNING and do not block the main write

#### Scenario: No reason supplied
- **WHEN** `archive_and_write()` is called without a `reason` argument
- **THEN** no sidecar is written
- **THEN** the archive snapshot stands alone

### Requirement: Optional rolling retention
The system SHALL prune older archive snapshots when a `max_archives` limit is set.

#### Scenario: Archive count below limit
- **WHEN** `archive_and_write()` is called with `max_archives=20` and the archive directory contains 15 snapshots
- **THEN** the new snapshot is added
- **THEN** no snapshots are deleted

#### Scenario: Archive count exceeds limit
- **WHEN** `archive_and_write()` is called with `max_archives=20` and the archive directory contains 20 existing snapshots
- **THEN** after the new snapshot is added, the oldest snapshots are deleted so that only the most recent 20 remain
- **THEN** deletion ordering is by filename (which encodes the UTC timestamp), mirroring the pattern in `events.py::rotate_log()`

#### Scenario: No retention limit
- **WHEN** `archive_and_write()` is called without `max_archives` (default `None`)
- **THEN** no snapshots are deleted regardless of directory size

### Requirement: Sentinel findings use archive helper
The system SHALL route `sentinel/findings.json` writes through `archive_and_write()` so that prior findings snapshots survive sentinel restarts.

#### Scenario: Findings update
- **WHEN** `SentinelFindings.add()`, `update()`, or `assess()` triggers a write
- **THEN** the call goes through `archive_and_write(path, content, reason="findings-update")`
- **THEN** a snapshot of the previous findings file is saved before the new one is written
- **THEN** the user can inspect historical findings after a sentinel restart

### Requirement: Sentinel status uses archive helper with retention
The system SHALL route `sentinel/status.json` writes through `archive_and_write()` with `max_archives=20` because status updates are frequent (every heartbeat).

#### Scenario: Status heartbeat
- **WHEN** `SentinelStatus.heartbeat()` triggers a write
- **THEN** the call goes through `archive_and_write(path, content, reason="status-update", max_archives=20)`
- **THEN** after many heartbeats, only the most recent 20 snapshots are retained
- **THEN** the active `status.json` always reflects the latest heartbeat

### Requirement: Coverage report uses archive helper
The system SHALL route `spec-coverage-report.md` regeneration through `archive_and_write()` so that the evolution of spec coverage is preserved.

#### Scenario: Coverage report regeneration
- **WHEN** the engine regenerates `spec-coverage-report.md` after a merge
- **THEN** the call goes through `archive_and_write(path, content, reason="coverage-regen")`
- **THEN** each prior coverage report is saved to the archive
- **THEN** the user can inspect coverage trends over time
