## Why

`relay-unwired-projects` made the fleet header name the registered projects whose sessions
bypass the question relay. It did not close the gap: a project registered without deploy
(`set-project register`, or the dashboard's add-project route) never gets the relay hooks,
because only `set-project init` runs `set-deploy-hooks`. Measured 2026-11-17 after the
header shipped: three registered projects listed as unwired, none with a
`.claude/settings.json`, one registered explicitly as no-deploy. The owner asked for the
hooks in those projects and for every project taken into the fleet to get them
automatically.

## What Changes

- `question_relay.wire_project(root)` adds whichever relay hook a project lacks into its
  machine-local `.claude/settings.local.json`, merging into what is there, and keeps that
  file out of git through `.git/info/exclude`. It never writes the project's tracked
  `settings.json` or `.gitignore`, never adds a hook already wired at any level (two relay
  hooks would post every question twice), and refuses to overwrite a local file it cannot
  parse.
- `set-project register` and `POST /api/projects` call it after registering. A failure is
  logged and never blocks the registration; the header still lists the project.
- `set-relay-wire <path>… | --registered [--dry-run]` runs it by hand, and is installed.

Not changed: `set-project init` keeps deploying the relay hooks into the tracked
`settings.json` through `set-deploy-hooks`.

## Capabilities

### Modified Capabilities

- `agent-question-relay`: projects registered without deploy are wired machine-locally.

## Impact

- `lib/set_orch/fleet/question_relay.py`, `lib/set_orch/fleet/relay_wire_cli.py`,
  `lib/set_orch/api/projects.py` (core, domain-free)
- `bin/set-relay-wire` (new), `bin/set-project` (`register`), `install.sh`
- Tests: `tests/unit/test_question_relay_unwired.py`
