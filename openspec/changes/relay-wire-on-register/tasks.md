## 1. Core (lib/set_orch)

- [x] 1.1 `wire_project()`: local file only, merge, no duplicate across levels, refuse an unreadable file, `.git/info/exclude` [REQ: a-project-taken-into-the-fleet-is-wired-machine-locally]
- [x] 1.2 `POST /api/projects` wires after saving; a failure is logged, never raised [REQ: a-project-taken-into-the-fleet-is-wired-machine-locally]
- [x] 1.3 Unit tests incl. the API route (fails without the wiring call) [REQ: a-project-taken-into-the-fleet-is-wired-machine-locally]

## 2. CLI

- [x] 2.1 `set-relay-wire` (`relay_wire_cli.py`), added to `install.sh` [REQ: a-project-taken-into-the-fleet-is-wired-machine-locally]
- [x] 2.2 `set-project register` calls it after registering [REQ: a-project-taken-into-the-fleet-is-wired-machine-locally]
      Checked 2026-11-17 in a sandbox config and a fresh repository: both hooks in the local file, the exclude line written, `git status` empty, the real registry untouched.
- [x] 2.3 The registered projects the header listed as unwired are wired with `set-relay-wire --registered`; the relay payload's `unwired` is then empty [REQ: a-project-taken-into-the-fleet-is-wired-machine-locally]
