## Why

The auto-clear cycle (handoff → `/clear` → reload → continue) runs only where somebody installed it
by hand: a handful of projects have hand-written watcher units, the rest have nothing, and so their
sessions fall to the runtime's native compaction, which keeps confidence and loses precision. The
owner decided on 2026-11-23 that auto-clear, not auto-compact, is the default **in every project**,
and that the machine doctor must know it belongs there. Today set-core neither installs it nor
notices its absence: nothing in `set-project init` or `set-doctor` names the handoff package at all.

## What Changes

- `set-project init` installs the auto-clear package by default in every registered project that
  is not archived and not `deploy: false`:
  - the package-owned templates (the package's own `init --auto-clear`), overwriting a file only
    when it is a known package version and keeping a locally modified one with a report line;
  - the two hooks the cycle needs (`SessionStart` matcher `clear|compact` reload, `PostToolUse`
    arm), merged additively into `.claude/settings.json` through the existing hook deploy — and
    **not** added when the project already wires its own reload or arm mechanism;
  - a systemd user unit `<project>-auto-clear.service` running the package's watcher with package
    defaults (no threshold or background flags), enabled and started; an existing unit is never
    rewritten, only reported when it carries flags that override the package defaults.
- `--dry-run` prints all of the above as a plan and writes nothing; a per-project opt-out
  (`auto_clear: false` in the registry entry) skips it with one line.
- `set-doctor` gains a per-project `auto-clear` check: WARN with the exact fix command when the
  templates are missing or stale, the hooks are not wired, the unit is missing or inactive, or the
  unit / a keep-going hook overrides the defaults with a threshold above the measured native
  compaction trigger; `skip` for archived, `deploy: false` and opted-out projects. Never `fail`.
- Recorded constraints from the coordination with the fleet session: one `/clear` executor per
  session (a later fleet rotation calls this executor rather than typing itself), and the arm nudge
  must skip short-lived fleet agents once they carry an identifying kind.

## Capabilities

### New Capabilities
- `auto-clear-install`: what `set-project init` installs for auto-clear, when it refuses to
  overwrite, how it detects a project's own mechanism, the unit it writes and starts, dry-run and
  opt-out.

### Modified Capabilities
- `machine-doctor`: a new per-project `auto-clear` check with WARN-plus-fix-command semantics.

## Impact

- `bin/set-project` (init flow), `lib/project/deploy.sh` (new deploy step), `bin/set-deploy-hooks`
  (two hooks added to the merged set, with own-mechanism detection), a new
  `templates/systemd/auto-clear.service` template.
- `lib/set_doctor/checks.py` (new check), its tests.
- Dependency: the `set-claude-handoff` checkout, resolved through the project registry like every
  other sibling; when it cannot be resolved, init says so and skips the step, the doctor WARNs.
- Running sessions in every project: a started watcher may type `/clear` into an idle, armed session
  past the threshold — that is the intended behaviour, and the reason the opt-out exists.
- No consumer is pushed and no CI is triggered: init writes files and starts a user unit only.
