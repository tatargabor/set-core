## Context

The handoff package (`set-claude-handoff`) owns the auto-clear cycle: a gate that only evaluates, a
watcher that is the only thing that types, a reload hook, an arm hook. It ships an installer
(`init --auto-clear`) that writes the templates and prints the settings snippet for the user to
merge; it never touches `settings.json` or systemd. On 2026-11-23 seven projects ran it, each with a
hand-written unit; the rest of the registry had nothing. The same day the package's defaults were
re-measured and moved (threshold 320k below the native compaction trigger at 366–372k; background
work no longer blocks; a one-time arm nudge), and the seven units had to be edited by hand because
each pinned the old values explicitly.

set-core already has the two mechanisms this needs: the additive hook merge in `bin/set-deploy-hooks`
(dedups by exact command string, keyed by matcher) and the registry-driven deploy in
`set-project init`. It has no reference to the handoff package anywhere.

Measured facts the decisions rest on:
- The reload/arm command strings the package prints are byte-identical to what the seven projects
  already carry, so the merge dedups them instead of adding a second copy.
- One project runs its own reload script for `clear|compact`; adding the package hook there would
  run two reloads.
- Two projects pass `--threshold 500000` to the package's keep-going hook in their own settings;
  with the native trigger near 370k that hook's "write the handoff at the limit" can never fire.
- Every hook file in the seven projects matched some shipped package version by blob hash, so the
  hash rule below would have overwritten none of their work.

## Goals / Non-Goals

**Goals:**
- Auto-clear present and running in every project the deploy reaches, without anyone writing a unit.
- No duplicate mechanism where a project has its own; no lost local edit; no rewritten hand unit.
- The doctor shows every gap with the command that closes it.

**Non-Goals:**
- Changing the gate, watcher or hooks (the package's).
- Committing or pushing in consumer repositories.
- A launchd equivalent for macOS (announced as skipped where `systemctl --user` is unavailable).
- Editing a project's keep-going arguments (reported by the doctor; the project changes its own
  settings).

## Decisions

### D1 — The package's installer writes into a scratch tree; set-core applies the overwrite rule
Init runs the package's own `cli.mjs init --auto-clear` in a temporary directory, then copies each
file it produced into the project only when the target is absent or matches a version the package
has shipped (blob hashes of every historical version, read from the package checkout's git history).
A file that matches none is kept and reported.
*Why:* the package stays the single owner of WHICH files exist (a second list in set-core would
drift the first time the package adds one), and set-core adds the one guarantee the package does not
give — its installer overwrites unconditionally.
*Alternative rejected:* running the installer in place — it would overwrite a hand-edited watcher.

### D2 — Hooks go through the existing additive merge, as a separate step with own-mechanism detection
The two entries use exactly the strings the package prints, so existing installs dedup. Before
merging, the step looks for a project-owned equivalent (a `SessionStart` command containing
`reinject` for the clear source; a `PostToolUse` command containing `handoff-arm`) and skips that
entry with a line. The entries are NOT added to the base hook set's "already canonical" check: a
project with its own reload must not look non-canonical on every run.

### D3 — A unit is created only where none exists, from a framework template
`templates/systemd/auto-clear.service` runs `<project>/.claude/hooks/watch-auto-clear.sh --dir
<project> --interval 60 --auto-continue default`, with no threshold, background or `--started-after`
flag. The start filter (the watcher's guard against clearing a session that started before its reload
hook was wired) is the package's: its `started-after-self-exclusion` change has `init --auto-clear`
write a wiring stamp, `.set/handoff/.reload-wired-at`, that the default filter reads. A unit-level
`--started-after <install time>` was the first design here and is rejected: measured by the package
session on 2026-11-23, a fixed start moment silently excludes the session that armed auto-clear
(2858 and 4926 skips in two trees). **Precondition for task 4.1:** that package change is shipped. An existing unit is
recognised by name OR by any user unit whose `ExecStart` runs that project's watcher (a hand unit may
be named differently); it is never rewritten, and its overriding flags are named with the edit that
would remove them.

### D4 — Order: templates, then hooks, then the unit
The unit starts last, and only when the reload hook is wired (by the package or by the project).
A watcher running against a project whose sessions cannot reload is the failure this ordering
prevents.

### D5 — The doctor's threshold warning compares against the effective compaction window
"Above the native trigger" is computed from `~/.claude/settings.json`: the default model's
`modelSettings.<model>.autoCompactWindow`, else the top-level `autoCompactWindow`, times 0.9 (the
measured trigger sat at 366–372k for a 400k window). Hard-coding 370k would be wrong the day the
window changes; the per-model key is the one that actually applied in the measurement (the
top-level key read 600000 at the same time, which is why a reader of only that key concluded the
opposite).

### D6 — Recorded constraints, not built here
One `/clear` executor per session: a fleet-side rotation, when built, supplies a reading and calls
this watcher, never types itself. The arm nudge must skip short-lived fleet agents once they carry
an identifying kind; until then a nudge into one is harmless noise.

## Risks / Trade-offs

- [The watcher now types into sessions in projects whose owner works by hand] → it clears only an
  idle, armed session past the threshold (arming needs a handoff written by that session), the
  nudge is once per session, and `auto_clear: false` opts a project out.
- [Dozens of watchers on one machine] → each is a 60 s bash loop; before the rollout, measure one
  watcher's CPU per day from `systemctl --user show -p CPUUsageNSec` and record it in the notes.
- [A package version change makes every project "stale" in the doctor at once] → that is correct
  (the doctor names the one command), and init is idempotent.
- [The package checkout is absent on a machine] → init skips with a line, the doctor warns.

## Migration Plan

1. Ship the init step and the doctor check; run `set-doctor` — every project without auto-clear
   shows WARN with its fix.
2. Run `set-project init --dry-run` across the registry and read the plan (templates kept, hooks
   skipped, units existing).
3. Run init project by project through the usual per-repo round; the resulting file changes are
   committed by each project's own session.
Rollback per project: `systemctl --user disable --now <project>-auto-clear.service` and
`auto_clear: false`; the templates and hooks are inert without the watcher.

## Open Questions

- Should the unit's auto-continue prompt be the package default everywhere, or may a project keep a
  custom one? (Today the seven hand units carry custom prompts; D3 leaves existing units alone, so
  this only decides what a NEW unit gets — the package default.)
