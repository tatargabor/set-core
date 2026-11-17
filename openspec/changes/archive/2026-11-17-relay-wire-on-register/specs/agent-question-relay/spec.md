## ADDED Requirements

### Requirement: A project taken into the fleet is wired machine-locally

`set-project register` and `POST /api/projects` SHALL, after registering a project whose
directory exists, add each relay hook it lacks — the `AskUserQuestion` relay hook and the
wait-detect `Stop` hook — to the project's `.claude/settings.local.json`, merged into that
file's existing content. A hook already wired in the user-level, project or local settings
SHALL NOT be added again. The project's tracked `.claude/settings.json` and `.gitignore`
SHALL NOT be written; the local file SHALL be kept out of git through the clone's
`.git/info/exclude` when no ignore rule already covers it. A local file that cannot be parsed
SHALL NOT be overwritten. A wiring failure SHALL NOT fail the registration.
`set-relay-wire` SHALL apply the same wiring to named directories or, with `--registered`,
to every registered project the relay lists as unwired.

#### Scenario: Registering a repository without deploy

- **WHEN** a git repository with no `.claude/` directory is registered with
  `set-project register`
- **THEN** its `.claude/settings.local.json` wires both hooks, `git status` shows no change,
  and the relay lists no unwired project for it

#### Scenario: The project already wires one hook

- **WHEN** the project's `settings.json` already wires the relay hook
- **THEN** only the wait-detect hook is added to the local file

#### Scenario: An unreadable local file

- **WHEN** the project's `.claude/settings.local.json` is not valid JSON
- **THEN** it is left byte-for-byte unchanged and the registration still succeeds
