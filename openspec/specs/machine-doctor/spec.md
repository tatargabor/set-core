# machine-doctor Specification

## Purpose
TBD - created by archiving change set-doctor. Update Purpose after archive.

## Requirements

### Requirement: Every check reports a status and the command that fixes it

`set-doctor` SHALL report each check as one record with a section, a name, a status (`ok`,
`warn`, `fail` or `skip`), a detail, and, when the status is `warn` or `fail`, the exact command
that fixes it. It SHALL exit 1 when any check is `fail`, and 0 otherwise. With `--strict` it
SHALL also exit 1 on `warn`. A `skip` SHALL carry its reason and SHALL NOT count as passing.
`--json` SHALL print `{"schema": "set-doctor/1", "ok", "counts", "checks"}`.

#### Scenario: A failing check sets the exit code
- **WHEN** one check fails and the rest pass
- **THEN** the exit code is 1, and the failing record carries a `fix`

#### Scenario: Warnings alone pass unless strict
- **WHEN** the only problems are warnings
- **THEN** the exit code is 0, and with `--strict` it is 1

### Requirement: The install is measured against the installer's own list

The install section SHALL read the list of commands from `install.sh` and check that each one
in the link directory resolves into this checkout. A missing command SHALL be `fail` with the
installer as the fix. A command that resolves into another checkout SHALL be `warn`. It SHALL
also check that the link directory is on `PATH` and that the MCP server's dependencies are
installed.

#### Scenario: A command the installer ships is missing
- **WHEN** one listed command has no link in the link directory
- **THEN** the install check fails, names that command, and gives `./install.sh` in the checkout as the fix

#### Scenario: A command links into another checkout
- **WHEN** a listed command resolves into a different directory
- **THEN** the install check warns and names it

### Requirement: The checkout is compared with its upstream

The checkout section SHALL report uncommitted files, and the number of commits ahead of and
behind the branch's upstream after a fetch. `--offline`, or a fetch that fails or times out,
SHALL still compare, and SHALL say the remote refs were not refreshed.

#### Scenario: Behind the remote
- **WHEN** the upstream has commits the checkout does not
- **THEN** the check warns with the count and `git -C <checkout> pull` as the fix

### Requirement: Every registered project is checked

For each registered project (or those matching `--project`) the doctor SHALL check: the path
exists and is a git repository (`fail` otherwise); the set-core version in
`.claude/.set-version` against this checkout (`warn` with the number of commits behind and
`set-project init` in that project as the fix, or `warn` when it was never deployed); the
set-core MCP registration in the Claude configuration (`warn` when missing, when its server
directory is not this checkout's, or when its `CLAUDE_PROJECT_DIR` is not the project);
`set-kb doctor` (its failures are this check's failures); and its bus wiring from `sac doctor`. A
registry entry with `"deploy": false` SHALL `skip` the deploy, MCP and bus checks, with the
reason.

#### Scenario: A registered path is gone
- **WHEN** a registry entry's path does not exist
- **THEN** that project's check fails and names the path

#### Scenario: A project behind this checkout
- **WHEN** a project's `.set-version` names a commit three commits behind this checkout
- **THEN** the deploy check warns "3 commits behind" with `set-project init` in that project as the fix

#### Scenario: An MCP registration that points elsewhere
- **WHEN** the project's set-core MCP registration sets `CLAUDE_PROJECT_DIR` to another directory
- **THEN** the MCP check warns and names both directories

#### Scenario: A data repository
- **WHEN** an entry carries `"deploy": false`
- **THEN** its deploy, MCP and bus checks are `skip` with "data repository", and its path and git checks still run

### Requirement: The MCP server is spoken to once

The doctor SHALL start the set-core MCP server of this checkout over stdio, send `initialize` and
call `kb_search` with `CLAUDE_PROJECT_DIR` set to a throwaway one-file repository, and report
`ok` only when the call returns a search page. A timeout or an error SHALL be `fail` with the
server's last error output.

#### Scenario: The server answers
- **WHEN** the MCP server starts and `kb_search` returns a page with the throwaway file as a hit
- **THEN** the MCP probe is `ok`

### Requirement: Tools, bus, provider and GitHub are checked without printing a secret

The doctor SHALL check python (at least 3.10), uv, node, jq, git, claude and the OpenSpec CLI
(at least the `generatedBy` version of the checkout's generated OpenSpec skills); the `sac`
launcher and the relay's reachability; whether the GLM provider resolves with a credential; and
`gh auth status`. No output, text or JSON, SHALL contain a credential value. `--live` SHALL add
the paid provider probe.

#### Scenario: A missing tool
- **WHEN** `jq` is not on PATH
- **THEN** the tools check fails for jq with an install hint

#### Scenario: The credential stays out of the output
- **WHEN** the provider configuration carries a credential
- **THEN** the provider check is `ok`, and neither the text nor the JSON output contains the credential

### Requirement: set-kb doctor reports linked projects

`set-kb doctor` SHALL include a `linked` check: `ok` when every entry in `config.linked`
resolves through the registry and loads, `warn` naming each one that does not (this project's
own search still works), and absent when the project links nothing.

#### Scenario: A linked project that is not registered
- **WHEN** the config links `gone` and the registry has no `gone`
- **THEN** `set-kb doctor` reports the `linked` check as a warning, naming `gone`
