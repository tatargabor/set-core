## ADDED Requirements

### Requirement: The share step names the editors and the owner account

*Asked for by the owner on 2026-11-08. A board must sit in an Artifact that everyone on the team can write.*

The tool SHALL read a machine-local editor list. Its path is `SET_WAVEBOARD_EDITORS`, or failing that
`~/.config/set-core/waveboard-editors.json`. The list is a JSON object with `owner_account` (a string) and `editors`
(a list of strings). The tool SHALL NOT write the list, and SHALL NOT copy any address from it into the job file, the
payload or a log line.

The tool SHALL read the account the session is signed in as from `oauthAccount.emailAddress` in
`$CLAUDE_CONFIG_DIR/.claude.json`, or in `~/.claude.json` when that variable is unset. When it cannot be read, the
account SHALL be reported as unknown.

The share step SHALL be printed by:
- `init` when it is given `--artifact-url`;
- `link`;
- `share [<job>...]`, for every named job, or for every job when none is named.

For a job with a page URL, the step SHALL name the URL, the claude.ai Share action, every editor with edit access, the
owner account, and the session's account. It SHALL say whether the session's account matches the owner account. For a
job without a page URL, `share` SHALL say that the board is not published.

When the list is missing or malformed, the step SHALL say so and show the expected shape. That SHALL NOT be an error:
the command's exit status is unchanged. With `--json` the same facts SHALL be returned as a `share` object.

#### Scenario: Linking a board names the editors

- **WHEN** the editor list names an owner and two editors, and `link <job> <url>` runs
- **THEN** the output carries a share line with the URL, both editors with edit access, and the owner account

#### Scenario: The session is not the owner account

- **WHEN** the session's account differs from `owner_account`
- **THEN** the share step says that the accounts differ, and names both

#### Scenario: No editor list

- **WHEN** no editor list exists at the resolved path
- **THEN** `link` still succeeds, and its output says the list is missing and where it belongs

#### Scenario: Nothing is persisted

- **WHEN** `init --artifact-url`, `link` and `sync` have run with an editor list present
- **THEN** neither the job file nor the payload contains any address from the list

### Requirement: A refused push asks for edit access

The push procedure in the Stop hook SHALL tell the agent what to do when the write is refused because its account
cannot write the Artifact. It SHALL say:
- ask the owner account named in the editor list (or, without a list, the account that published the board) for edit
  access through claude.ai Share;
- say so in one line, and continue.

The procedure SHALL NOT advise `SET_WAVEBOARD_PUSH=off`. The switch itself SHALL keep working.

#### Scenario: The procedure names the owner

- **WHEN** a job is pending, the editor list names an owner, and the hook blocks
- **THEN** the reason names that owner account and edit access, and does not contain `SET_WAVEBOARD_PUSH=off`

### Requirement: An item can depend on another board's item

An item MAY carry `depends_on`: a list of references, each `{"job": J, "item": I}` with an optional `"project": P`.
- Without `project`, a reference points into the same repository.
- With `project`, the project SHALL be resolved through the set-core registry, the same way `project` evidence is.
- Job and item SHALL be valid ids.
- A reference to the item itself SHALL be refused.

Dependencies SHALL be set in three ways:
- `add --depends-on <ref>`, which may be repeated;
- `depend <job> <item> <ref>...`;
- `undepend <job> <item> <ref>...`.

A reference is written `[project:]job/item`. A malformed reference SHALL exit 2 and leave the file unchanged. Adding a
reference that is already there SHALL change nothing.

#### Scenario: Adding a cross-project dependency

- **WHEN** `depend j a other:k/b` runs
- **THEN** item `a` of job `j` carries `{"project":"other","job":"k","item":"b"}` in `depends_on`

#### Scenario: A malformed reference

- **WHEN** `depend j a not-a-ref` runs
- **THEN** the command exits 2 and the job file is unchanged

### Requirement: A dependency is met only by a done item, and never by an unknown one

A reference SHALL be met when the item it names exists and its status is `done`. It SHALL be unmet in every other
case:
- any other status, `skipped` included;
- the project is not registered here, or its directory is missing;
- the job file is missing or unreadable, or the item is missing.

An unmet reference that cannot be resolved SHALL carry a reason and a null status.

#### Scenario: The prerequisite is done

- **WHEN** an item depends on an item whose status is `done`
- **THEN** the dependency is met and the item is not waiting

#### Scenario: The prerequisite was skipped

- **WHEN** the referenced item is `skipped`
- **THEN** the dependency is unmet and reports status `skipped`

#### Scenario: An unregistered project

- **WHEN** a reference names a project that is not in this machine's registry
- **THEN** the dependency is unmet with a reason, never met

### Requirement: The payload carries what each item waits on and what it blocks

`sync` SHALL add two computed lists to each item of the payload:
- `waiting_on`, when the item is neither `done` nor `skipped`: its unmet references, each with `status` and `reason`;
- `blocks`: every item on a board of any registered project, or of this repository, whose `depends_on` names this
  item, each with its project, job, item and status.

Both lists SHALL be part of the hashed content. This repository SHALL be matched by every registry name whose path
resolves to its root, and by references without a project. Neither list SHALL be written into the job file, and the
scan SHALL NOT run git.

#### Scenario: The other board finishes

- **WHEN** a pushed board has an item waiting on another board's item, and that item becomes `done`
- **THEN** the next sync drops the reference from `waiting_on`, the content hash changes, and the job is pending a push

#### Scenario: Shown on both boards

- **WHEN** item `a` of job `j` depends on item `b` of job `k`, in the same repository
- **THEN** the payload of `j` lists `k/b` under `a`'s `waiting_on`, and the payload of `k` lists `j/a` under `b`'s
  `blocks`

### Requirement: A waiting item cannot be started by report

`set <job> <item> doing` and `set <job> <item> done` SHALL exit 2 and name the unmet references when the item has any.
With `--force`, the status SHALL be set. `todo`, `blocked` and `skipped` SHALL always be allowed. A status that sync
derives from evidence SHALL NOT be guarded.

#### Scenario: Refused without force

- **WHEN** an item waits on an unmet reference and `set <job> <item> done` runs
- **THEN** the command exits 2, names the reference, and the job file is unchanged

#### Scenario: Forced

- **WHEN** the same command runs with `--force`
- **THEN** the item's status becomes `done`

### Requirement: The page shows waits-on and blocks

The board page SHALL draw an item that is `todo` and has a non-empty `waiting_on` as blocked:
- with the blocked chip colour;
- in the blocked Kanban column;
- as a blocked segment, counted as blocked.

It SHALL add a "waits on" chip listing each reference as `project/job/item` with its status or reason. An item that is
`doing` with a non-empty `waiting_on` SHALL keep its status and also show the chip. An item with a non-empty `blocks`
SHALL show a "blocks N" chip whose tooltip lists the references, and says that they were read on the machine that
synced. A payload without these fields SHALL render as it did before.

#### Scenario: A waiting todo item

- **WHEN** the state holds a `todo` item with one entry in `waiting_on`
- **THEN** the Waves view shows it with the blocked chip and a waits-on chip, and the Kanban view shows it in the
  blocked column

#### Scenario: An old payload

- **WHEN** the state has no `waiting_on` or `blocks` fields
- **THEN** every item renders in its own status, as before

### Requirement: `overview` is the combined view over every registered project

`set-wave-board overview` SHALL read every registered project's `docs/waveboard/*.json` and print:
- one line per board, with its counts, its waiting items and the items it blocks;
- one line per dependency edge, saying met or unmet, with the reason when unresolved.

With `--json` it SHALL return `boards` and `edges`. A file that cannot be read SHALL be listed with a reason, never left
out. It SHALL NOT write anything.

#### Scenario: Two projects linked by one edge

- **WHEN** project A's board has an item depending on project B's item, which is `doing`
- **THEN** `overview --json` lists both boards and one edge from A to B with `met` false
