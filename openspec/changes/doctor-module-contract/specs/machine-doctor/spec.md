## MODIFIED Requirements

### Requirement: Every check reports a status and the command that fixes it

`set-doctor` SHALL report each check as one record with a section, a name, a status (`ok`,
`warn`, `fail` or `skip`), a detail, and, when the status is `warn` or `fail`, the exact command
that fixes it. A record produced by a module doctor SHALL also carry `module`. A record about one
registered project SHALL carry `project`. It SHALL exit 1 when any check is `fail`, and 0
otherwise. With `--strict` it SHALL also exit 1 on `warn`. A `skip` SHALL carry its reason and
SHALL NOT count as passing. `--json` SHALL print `{"schema": "set-doctor/1", "ok", "counts",
"checks"}`. The `module` field is an addition within `set-doctor/1`, not a new schema.

#### Scenario: A failing check sets the exit code
- **WHEN** one check fails and the rest pass
- **THEN** the exit code is 1, and the failing record carries a `fix`

#### Scenario: Warnings alone pass unless strict
- **WHEN** the only problems are warnings
- **THEN** the exit code is 0, and with `--strict` it is 1

#### Scenario: A module's record says where it came from
- **WHEN** a record in the JSON output was produced by the agent-bus module doctor
- **THEN** it carries `"module": "sac"`

### Requirement: Every registered project is checked

For each registered project (or those matching `--project`) whose path is a git repository, the
doctor SHALL check:
- the set-core version in `.claude/.set-version` against this checkout: `warn` with the number of
  commits behind and `set-project init` in that project as the fix, or `warn` when it was never
  deployed;
- the set-core MCP registration in the Claude configuration: `warn` when missing, when its server
  directory is not this checkout's, or when its `CLAUDE_PROJECT_DIR` is not the project;
- the records every module doctor reports for that project (`set-kb doctor` and `sac doctor`
  included), at the module's status.

A registry entry with `"deploy": false` SHALL `skip` the deploy, MCP and bus checks, with the
reason.

Registry entries whose path no longer exists, and entries whose directory exists but is not a git
repository, SHALL be reported together as ONE `warn` record named `stale`, in the projects section.
It SHALL give their count, and name each entry with its reason (gone / not a git repository). Its
fix SHALL deregister exactly those entries. They SHALL NOT each be reported as a `fail`, and SHALL
NOT be checked further.

The bus records SHALL be derived from the agent-bus module's per-project hooks and live seats.
- A project with at least one live seat that has no `session-start` hook or no `watch-guard` hook
  SHALL be a `fail`. Its detail SHALL name the live seat(s) and the missing hook(s).
- A project without hooks and without a live seat SHALL be a `warn`.
- A hook kind wired by more than one carrier SHALL be a `warn` naming the carriers, because each
  carrier runs the hook.

#### Scenario: A registered path is gone
- **WHEN** one registry entry's path does not exist and another's directory has no git repository
- **THEN** the report has one `stale` warn naming both entries with their reasons and a fix that deregisters both, and no `fail` for either

#### Scenario: A project behind this checkout
- **WHEN** a project's `.set-version` names a commit three commits behind this checkout
- **THEN** the deploy check warns "3 commits behind" with `set-project init` in that project as the fix

#### Scenario: An MCP registration that points elsewhere
- **WHEN** the project's set-core MCP registration sets `CLAUDE_PROJECT_DIR` to another directory
- **THEN** the MCP check warns and names both directories

#### Scenario: A data repository
- **WHEN** an entry carries `"deploy": false`
- **THEN** its deploy, MCP and bus checks are `skip` with "data repository", and its path and git checks still run

#### Scenario: A live session in a project off the bus
- **WHEN** the agent-bus module reports a project with a live seat and no hooks at all
- **THEN** that project's bus record is a `fail` naming the seat and the missing `session-start` and `watch-guard` hooks, with `sac install` in that project as the fix

#### Scenario: A live session without the watch guard
- **WHEN** a project with a live seat has `session-start` wired but no `watch-guard`
- **THEN** the bus record is a `fail` naming `watch-guard`

#### Scenario: Off the bus and idle
- **WHEN** a project has no hooks and no live seat
- **THEN** the bus record is a `warn`, as before

#### Scenario: A hook wired twice
- **WHEN** a project's `session-start` hook comes from both its settings file and an installed plugin
- **THEN** the bus record warns that `session-start` runs from two carriers and names both
