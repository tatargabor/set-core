# set-watchdog — the fleet's continuous self-check

`set-doctor` answers "is this machine set up right?" when somebody asks. `set-watchdog` asks
it all day, on its own, and adds the behaviour `set-doctor` cannot see: things that are only
wrong *over time*. Change: `openspec/changes/fleet-watchdog`.

## How it runs

A **stateless tick** every 5 minutes, run by the `set-watchdog.timer` user unit (`install.sh`
installs and enables it). A tick is a fresh process: it loads the finding store, runs the
**due** probes, triages what is new, dispatches what is real, writes the store, and exits.
Nothing grows across a day, which is the point: a resident agent session doing this would pay
the context and cache costs it is meant to watch for.

```bash
set-watchdog status            # badge state, counts, open findings
set-watchdog status --json     # the same as GET /api/fleet/watchdog (set-watchdog/1)
set-watchdog tick [--force]    # one tick now (--force: every probe, not only the due ones)
set-watchdog probes            # the probes and their intervals
set-watchdog mute <fp> --days N
set-watchdog dispatch <fp>     # hand an open finding to its owner now (skips the mode, not the
                               # one-open-dispatch rule)
```

In the fleet header the **stethoscope badge** shows the open count, red when any finding is a
`fail`, and a dashed **stale** state when the last tick is older than three intervals or none
was ever recorded. Stale is not zero, because a dead watchdog must not look like a calm machine.
The badge opens a floating panel with the findings, their triage and dispatch state, and the
mute and dispatch-now actions. `set-doctor` reports a `fleet / watchdog` record as well (timer
active, last tick fresh).

## Probes

| probe | every | finds |
|---|---|---|
| `wake-storm` | 10 min | an idle session (no typed prompt for ≥ 60 min) woken by the bus ≥ 3× in 2 h, while it has no open request of its own. Read from the transcript's turn-start markers (`origin.kind`, the inbox-watch task notification, the bus Stop-hook continuation); it warns when it cannot classify turn starts at all |
| `auto-clear-miss` | 5 min | a live session at or above its auto-clear threshold (the unit's `--threshold`, else the watcher package's default) for longer than 15 min with the same session id, i.e. no clear |
| `relay-hold` | 5 min | a relayed question (not a continuation) held longer than 15 min **although a prompt was typed into its terminal** (counted from the transcript's queued-prompt records). A hold with nothing typed is the owner not having answered yet, which the relay already surfaces, so it is not reported; an unreadable transcript is reported with the count unknown |
| `service-health` | 5 min | set-web not answering, the agent owner or the bus unreachable, any user unit `failed` (owner resolved from its `ExecStart` path; the finding carries the unit's `Result` and exit status), an armed auto-clear watcher not active |
| `doctor-delta` | 30 min | a `fail` record in `set-doctor --json` (module doctors included) that was not failing at the probe's first run. That is how a project family adds its own invariants: declare a module doctor in `doctors.d`, and the watchdog needs no second extension point |

A probe that cannot read its source reports a `warn`. It never reports silence. One finding is
kept per `sha256(probe + subject)`. A finding **resolves** when its probe runs and no longer
reports it. A finding that is not looked at does not resolve.

## Triage and dispatch

Only a tick that **opened** findings makes a model call: one batched `set-glm -p` (hooks off,
no session persisted). Its input is shape-only: probe, severity, subject, summary, evidence
(counts, durations, ids, unit names, project slugs), and the titles of the open bug-register
entries. It carries no transcript text, no message body, and no file content. The answer per
finding is `real`, `noise` or `known:B-<n>`, plus an owner and a fix brief. A finding stays
`untriaged`, and visible, whenever the daily cap is reached, GLM is unreachable, the answer
cannot be parsed, or the brief answered for a finding names another finding of the same call first
(the answer is keyed by the fingerprint the model returns, and on the first live day two briefs
came back swapped). Untriaged is never treated as noise.

A `real` finding is handed to its **owning project's** agent through `set-fleet-ask` (seat
`set-watchdog`). The fleet starts a desk if none is live, and the desk runs on the project's
default provider, never GLM. The brief tells the agent to verify the finding first, register
it, fix it, prove the fix and report back. It may not deploy anything or send anything outward.
A probe's owner hint that names a registered project (a unit's `ExecStart` tree, a module
doctor's project) outranks the model's guess. Limits that hold in every mode: one open dispatch
per fingerprint, `watchdog.dispatch_daily` sends per day, and a 24 h cooldown before a
fingerprint that came back is re-sent.

## Configuration (`set-config set <key> <value>`)

| key | default | |
|---|---|---|
| `watchdog.enabled` | `true` | kill switch: a tick exits at once, logged |
| `watchdog.remediation` | `auto` | `off` · `notify` (show only) · `propose` (offer dispatch-now) · `auto` |
| `watchdog.dispatch_daily` | `3` | |
| `watchdog.triage_daily_calls` | `60` | |
| `watchdog.triage_max_chars` | `8000` | prompt cap; titles are halved first, then findings deferred |
| `watchdog.probe.<name>.interval_s` | per probe | minimum 60 |
| `watchdog.wake_storm.{window_s,count,idle_s}` | `7200`, `3`, `3600` | |
| `watchdog.auto_clear.grace_s` | `900` | |
| `watchdog.relay_hold.bound_s` | `900` | |

## What it stores, and where

`~/.local/share/set-core/watchdog/` (mode 700/600; `SET_WATCHDOG_DIR` overrides it):
`findings.json` (one record per fingerprint, shape-only, resolved ones kept 14 days) and
`ticks.jsonl` (one line per tick: counts and durations, no evidence). Nothing is written into a
repository. The unit's journal carries ids, counts and project slugs, never evidence text.
