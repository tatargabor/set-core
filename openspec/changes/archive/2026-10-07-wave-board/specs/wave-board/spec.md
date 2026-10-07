# wave-board

## IN SCOPE

- A per-job registration file in the consumer repository, and its schema
- Status derived from deterministic evidence, and its precedence over manual status
- Evidence from another registered project, resolved by name
- An idempotent sync that writes a database payload and says when a push is needed
- The machine-local record of what was pushed
- A Stop hook that makes the agent push, with a backoff and a loop guard
- A read-only board page with an offline fallback
- Delivery of the hook to projects initialised before this capability existed

## OUT OF SCOPE

- Writing the Artifact database from a script or a hook — the platform does not allow it
- Publishing or sharing the Artifact page automatically
- Editing the board from the page; the page never writes
- Scheduling, assignment, estimates, or any product-roadmap concept

## ADDED Requirements

### Requirement: A job is a tracked registration file

Each job SHALL be one JSON file at `docs/waveboard/<job>.json` in the consumer repository,
tracked in git, with `schema` equal to `set-wave-board/1`, a slug `job`, a `title`, an
`artifact_url` (null until the board page is published), a `created` date, and an ordered list
of `waves`, each with an `id`, a `title` and an ordered list of `items`. Each item SHALL carry
`id`, `title`, `status` (one of `todo`, `doing`, `done`, `blocked`, `skipped`), `evidence`
(null or an evidence object), `note`, `updated` and `by`.

The file SHALL NOT contain an absolute path. A path inside it is relative to the repository
root, and another project is named by its registry name.

#### Scenario: Creating a job and adding an item

- **WHEN** `set-wave-board init <job> --title T` runs and then
  `add <job> --wave w0 --item a --title A` runs
- **THEN** `docs/waveboard/<job>.json` exists with one wave `w0` holding item `a` at status
  `todo`

#### Scenario: Evidence that is malformed is refused when added

- **WHEN** `add` is given evidence of an unknown type, or one missing a required field
- **THEN** the command exits non-zero and the job file is unchanged

### Requirement: Status is derived from evidence

`sync` SHALL evaluate each item's evidence in the repository root
(`git rev-parse --show-toplevel`) and derive a status from it:

- `openspec-tasks` (`path`): every box checked → `done`, some → `doing`, none → `todo`; when
  the path is gone but `openspec/changes/archive/*-<change>/tasks.md` exists → `done`.
- `path-exists` (`path`): the path exists → `done`.
- `commit` (`grep`): `git log --grep` on `HEAD` finds a commit → `done`.

Absence of evidence SHALL NOT be a verdict: a missing path, a missing tasks file with no
archive, or no matching commit leaves the item's status as it is. Absence cannot tell "not yet"
from "not on this machine", and reporting the second as the first would undo a correct status.

#### Scenario: Partly checked tasks file

- **WHEN** an item's `openspec-tasks` file has some boxes checked and some not
- **THEN** sync sets the item to `doing`

#### Scenario: Archived change

- **WHEN** the change directory is gone and an archived copy of its `tasks.md` exists
- **THEN** sync sets the item to `done`

#### Scenario: No evidence yet

- **WHEN** an item's `path-exists` path does not exist and the item was set to `doing` by hand
- **THEN** sync leaves it at `doing`

### Requirement: Evidence wins, except a manual block or skip

When evidence yields a status, that status SHALL replace the item's status, with one exception:
an item whose status is `blocked` or `skipped` SHALL keep it. A block or a skip is a human
decision that no evidence can see.

#### Scenario: An agent's premature done is corrected

- **WHEN** an item was set to `done` by hand and its tasks file still has unchecked boxes
- **THEN** sync sets it to `doing`

#### Scenario: A blocked item stays blocked

- **WHEN** an item is `blocked` and its evidence says `done`
- **THEN** sync leaves it `blocked`

### Requirement: Evidence from another project is resolved by registry name

Evidence of type `project` SHALL name a project and carry nested evidence; the nested evidence
SHALL be evaluated with that project's root as the base. The name SHALL be resolved through the
set-core registry (`SET_CORE_REGISTRY`, default `~/.config/set-core/projects.json`). When the
name is not registered on this machine, or its path does not exist, the item's status SHALL be
left unchanged and the item SHALL be reported as unresolved. Nested `project` evidence SHALL be
refused.

#### Scenario: A registered project

- **WHEN** the named project is registered and its nested evidence is satisfied
- **THEN** sync sets the item to `done`

#### Scenario: A project not registered here

- **WHEN** the named project is not in this machine's registry
- **THEN** the item's status is unchanged and sync reports it as unresolved

### Requirement: Sync is idempotent and writes the database payload

`sync` SHALL rewrite a job file only when its content changed, with stable formatting, and
SHALL change an item's `updated` and `by` only when its status changed. It SHALL write the
database payload to `.set/waveboard/<job>.state.json` — `{schema, job, title, waves,
synced_at, synced_by, content_hash}` — only when the content hash differs from the payload
already there. When the job has an `artifact_url` and the payload's hash differs from the last
pushed hash, it SHALL print `PUSH <job> <artifact_url> <payload-path>` on standard output.
The tool SHALL keep `.set/waveboard/` out of git on its own.

#### Scenario: A second sync changes nothing

- **WHEN** sync runs twice with no change in evidence or in the job file
- **THEN** the second run rewrites neither file and, once the first payload has been recorded
  as pushed, prints no `PUSH` line

### Requirement: The push is the agent's act, recorded per machine

Only the agent can write the Artifact database, so the tool SHALL NOT attempt it. After the
agent writes the payload as document `state` in collection `board`, `set-wave-board pushed
<job> --version N` SHALL record the pushed hash and the database version in
`.set/waveboard/<job>.pushed.json`. `pending` SHALL list every job with an `artifact_url` whose
current payload hash differs from the recorded one.

#### Scenario: Push cycle

- **WHEN** a job's payload changed, then `pushed` is recorded for it
- **THEN** `pending` lists it before the record and does not list it after

### Requirement: A Stop hook makes the agent push

`set-hook-waveboard` SHALL run on the Stop event. It SHALL exit 0 without output when
`stop_hook_active` is true, outside a git repository, in a linked git worktree (unless
`SET_WAVEBOARD_PUSH=worktree`), when `docs/waveboard/` does not exist, or when
`SET_WAVEBOARD_PUSH=off`. Otherwise it SHALL run sync quietly and, for each pending job not
reminded within the backoff (default 30 minutes, timestamp in `.set/waveboard/<job>.nag`),
print one `{"decision":"block","reason":...}` whose reason is the exact push procedure: the
`ArtifactData` `set` call with the URL, `collection=board`, `doc_id=state`, the payload path,
and `if_version` (the last recorded version, or omitted when none is recorded), what to do on
a version conflict, and the `pushed` command to run after. It SHALL NOT use the network and
SHALL finish well inside its timeout.

#### Scenario: The hook's own continuation does not loop

- **WHEN** the Stop event carries `stop_hook_active: true`
- **THEN** the hook prints nothing and exits 0

#### Scenario: A linked worktree is not the board's source

- **WHEN** the Stop event comes from a linked git worktree of a repository with a pending job
- **THEN** the hook prints nothing

#### Scenario: Backoff

- **WHEN** the hook blocked for a job and runs again within the backoff with the job still
  pending
- **THEN** it prints nothing

### Requirement: The board page is read-only and works offline

The page SHALL render waves, items and status chips, done and remaining counts per wave and
overall, and the last sync time and machine. It SHALL subscribe to `board/state` through the
`db` capability and SHALL fall back to the embedded `<script type="application/json"
id="seed">` when the database is unavailable. It SHALL NOT write. `set-wave-board render`
SHALL produce the page with the current payload as the seed.

#### Scenario: Offline render

- **WHEN** `render <job> -o board.html` runs and the file is opened without the platform
- **THEN** the page shows the job from the seed and says it is a snapshot

### Requirement: The hook reaches existing projects

`set-deploy-hooks` SHALL add `set-hook-waveboard` to the Stop array, and SHALL treat a settings
file without it as not canonical, so a project initialised before this capability receives it
on its next `set-project init`. The merge SHALL keep every project-owned hook, and running it
twice SHALL add the hook once. `install.sh` SHALL link `set-wave-board` and
`set-hook-waveboard` into the install directory it puts on `PATH`.

#### Scenario: A project that already has the base hooks and its own

- **WHEN** a settings file carries the base hooks and a project-owned Stop hook, and
  `set-deploy-hooks` runs twice
- **THEN** the project hook is still there and `set-hook-waveboard` appears exactly once
