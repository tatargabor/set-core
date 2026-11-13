## MODIFIED Requirements

### Requirement: Sync is idempotent and writes the database payload

`sync` SHALL rewrite a job file only when its content changed, with stable formatting, and
SHALL change an item's `updated` only when its status changed. It SHALL write the
database payload to `.set/waveboard/<job>.state.json` — `{schema, job, title, waves,
synced_at, content_hash}` — only when the content hash differs from the payload
already there. Neither this payload, the combined payload, nor the combined seed SHALL carry a
machine name. When the job has an `artifact_url` and the payload's hash differs from the last
pushed hash, it SHALL print `PUSH <job> <artifact_url> <payload-path>` on standard output.
The tool SHALL keep `.set/waveboard/` out of git on its own.

#### Scenario: A second sync changes nothing

- **WHEN** sync runs twice with no change in evidence or in the job file
- **THEN** the second run rewrites neither file and, once the first payload has been recorded
  as pushed, prints no `PUSH` line

#### Scenario: The payload names no machine

- **WHEN** sync writes the state payload
- **THEN** the payload has no `synced_by` field and carries `synced_at`

### Requirement: An agent can record that a board was reviewed

`set-wave-board reviewed <job>` SHALL set `reviewed` to `{"at": <now, ISO UTC>}` at the top level
of the job file, and change nothing else in it. A legacy `reviewed.by` SHALL be dropped on the
next write of the job file. The `reviewed` field SHALL NOT be part of the content that is hashed
and pushed. A review SHALL therefore never make a job pending a push, and `sync` SHALL keep the
field as it is.

#### Scenario: A review resets staleness

- **WHEN** a job is stale and `reviewed` is run for it
- **THEN** `stale` reports `commits_since_change` 0 and `stale` false

#### Scenario: A review records no machine

- **WHEN** `reviewed` is run for a job whose file carries a legacy `reviewed.by`
- **THEN** the job file's `reviewed` holds `at` and no `by`

#### Scenario: A review does not cause a push

- **WHEN** a job's payload has been recorded as pushed and `reviewed` is then run and `sync` runs
- **THEN** `pending` does not list the job, and the job file still carries the `reviewed` stamp
