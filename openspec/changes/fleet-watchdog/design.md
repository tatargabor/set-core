## Context

The fleet's quiet failures are found by accident: the wake that re-reads a context every half hour,
the auto-clear watcher that stops acting, the relayed question held behind a busy-looking terminal,
the user timer that went `failed`. `set-doctor` sees static state, but only when somebody runs it,
and it never looks at behaviour over time. The pieces a watchdog needs already exist and are
measured:

- **The fleet payload** (`GET /api/fleet/agents`) carries every live agent, grouped by project, with
  its measured model, context fill (`context_fill.py`) and cache heat (`cache_heat.py`).
- **Transcripts tell a wake from a person.** Measured 2026-11-24 over the 60 most recent
  transcripts on one machine: a typed prompt carries `origin.kind = "human"`. A background shell
  exiting (the inbox watch included) carries `origin.kind = "task-notification"`, and its
  `<summary>` names the command's description. A bus Stop-hook continuation is an `isMeta` record
  whose text starts with `Stop hook feedback: [set-agent-comm]`. A tool result carries
  `toolUseResult`. Only these markers are read. Message text is never read beyond those prefixes.
- **The auto-clear threshold** is the watcher package's default unless the unit's `ExecStart`
  carries `--threshold` (`templates/systemd/auto-clear.service`, `auto_clear_deploy.OVERRIDING`).
- **The relay's waiting records** and `relay.log` live in the relay's state dir
  (`question_relay.state_dir()`).
- **`set-doctor --json`** speaks `set-doctor/1` and merges module doctors from `doctors.d`
  (`doctor-module-contract`).
- **GLM** is reached through `set-glm -p … --output-format json`, with the parameters resolved by
  `set_orch.providers` from `providers.json`.
- **Periodic jobs** here are user timers (`set-fleet-idle-close.timer`). **Cross-project requests**
  go through `set-fleet-ask`, which opens an engagement and starts a desk when the project has no
  live seat.

## Goals / Non-Goals

**Goals:**
- Notice the quiet failures within minutes, all day, at a token cost that stays negligible.
- Show the state where the owner already looks, the fleet header. A dead watchdog must look dead.
- Start the repair automatically, in the project that owns the defect, with a Claude agent.

**Non-Goals:**
- A watchdog that edits code, merges, deploys, or messages a person.
- Replacing `set-doctor`. The watchdog runs it; it does not re-implement it.
- Open-ended "find anything strange" log reading by a model in this round (see Open Questions).

## Decisions

**D1 — A stateless tick on a timer, not a resident agent session.** Each tick is a fresh process:
load the store, run the due probes, triage, dispatch, write, exit. *Alternative:* a fleet-visible
GLM chat session that loops all day. Rejected: its context grows with every observation, so it
needs its own auto-clear and handoff. It is subject to the very wake and cache costs it watches
for, and its "memory" of open findings would be a transcript instead of a file. The fleet still
*sees* the watchdog, through its badge and panel (D6), and the fix agents it starts are ordinary
fleet agents.

**D2 — Probes are deterministic Python. The model only judges what they found.** Every
observation is a measurement: counts from transcripts, fill from the payload, unit state from
`systemctl --user`, ages from the relay's records. A probe costs zero tokens, so the tick can run
every 5 minutes. *Alternative:* hand logs to GLM and ask "anything wrong?". Rejected for this
round: it is unbounded in tokens, it is non-reproducible, and it would send log content off the
machine.

**D3 — The fingerprint is `sha256(probe + subject)`, and the evidence is updated in place.** One
anomaly is one finding, however many ticks see it. Resolution is the probe running and not
reporting it, which is a measurement. A finding that is simply not looked at does not resolve.
A muted fingerprint is still stored, and its recurrence is listed under muted, so a mute cannot
hide a change of severity. A mute is per fingerprint, so a new subject is a new finding.

**D4 — Triage is one batched GLM call per tick, only when something new opened.** On a calm
machine that is zero calls a day. The input is the new findings' shape-only fields plus the
**titles** of the open bug-register entries, read from the owning project's register when it has
one, so `known:B-…` can be answered without the bodies. The answer is JSON. A parse failure leaves
the finding `untriaged`, never `noise`: the fail direction of a bad answer must be "shown", not
"hidden". *Alternative:* triage with a local rule table. That stays possible as a probe-level
`owner` hint, and the model is there for the owner and fix brief that a rule table cannot write.

**D5 — Remediation is a request to the owning project, made through the existing engagement path.**
`set-fleet-ask <owner> "<brief>"` creates an engagement, so the panel can show *answered or not*
from the bus's own link instead of a second record. The fix agent runs on the project's default
(Claude) provider. The watchdog passes no provider override, and the brief states the rules:
register, fix, prove (stash-and-rerun), report, no deploy, no outward message. Working in another
project's tree is that project's own agent working in its own tree, which is coordination between
the owner's agents, not this process writing elsewhere. The limits (one open dispatch per
fingerprint, a daily cap, a 24 h cooldown after an unresolved dispatch) hold in every mode, so
`auto` cannot become a storm of its own.

**D6 — The UI is a header badge plus an overlay panel, with four badge states.** The states are
*ok* (zero open), *count*, *red count* (any open `fail`) and *stale* (the last tick is older than
3 × interval, or none was ever recorded). *Stale* is rendered differently from zero. That is the
"a gap is not a zero" rule: a stopped timer must not read as a calm machine. The panel floats and
never pushes (ui-quality). A failure count stays on the badge while the panel is closed.

**D7 — What leaves the machine.** GLM is an external provider. The triage input is bounded to
probe names, severities, project slugs, session ids, unit names, counts, durations and bug-register
**titles**. Titles are the owner's own text about framework behaviour. No transcript text, no
message body, no file content. The finding store holds the same shape-only data, mode 600, under
`~/.local/share/set-core/watchdog/`. The dispatch brief does go to a Claude agent, but on the
owner's own bus, and it carries only the same fields.

**D8 — Layering.** The tick, the store, triage and dispatch are framework mechanics in
`lib/set_orch/watchdog/`. The built-in probes watch set features (bus, auto-clear, relay, fleet
services) and hold no project-type knowledge, so they belong in Layer 1 as well. Anything specific
to a project or project type arrives as a module doctor through `doctors.d` (D2 of
`doctor-module-contract`) and reaches the watchdog only through `set-doctor --json`.

## Risks / Trade-offs

- [The wake-storm probe counts the agent's own background tasks as wakes] → Count only
  task-notifications whose summary names the inbox-watch description, plus the bus Stop-hook
  continuations, and only in windows with no human prompt. Hold this with a fixture made from the
  measured record shapes.
- [A Claude Code update renames `origin` or the Stop-hook prefix, and the probe goes silent] →
  When a live session's transcript shows no recognisable turn-start marker at all over a window,
  the probe reports a `warn` "cannot classify turn starts". It never reports zero wakes.
- [Auto-dispatch fixes the wrong thing, or the same thing twice] → One open dispatch per
  fingerprint, a daily cap of 3, and a cooldown. Every dispatch is an engagement the owner can see
  and withdraw. `propose` is one config line away.
- [The triage budget is exhausted on a bad day] → Findings stay visible as `untriaged`. The cap
  is per day, and the badge does not depend on triage.
- [The watchdog itself dies] → The *stale* badge state plus the `set-doctor` `watchdog` record.
  Both are measured from the tick log, not from the unit's own claim.
- [The tick overlaps a slow `set-doctor`] → The lock. `doctor-delta` runs on its own 30-min
  interval with a timeout.

## Migration Plan

New and additive. `install.sh` installs `set-watchdog`, writes `set-watchdog.{service,timer}`
from `templates/systemd/`, and enables the timer. Rollback: `systemctl --user disable --now
set-watchdog.timer`. The kill switch is `watchdog.enabled false` in `set-config`, which makes a
tick exit at once, logged.

## Open Questions

- **An hourly open-ended scan** (GLM reads an aggregated metrics digest, not logs, and names
  anomalies no probe covers). Deferred until the deterministic probes have run for a week and their
  noise rate is measured. It would be a probe like the others, with its own budget line.
- **Rate the triage.** The fix outcomes (resolved after dispatch, or not) give a live accuracy
  figure for GLM triage, the way auto-answer records its pairs. The data is kept from the start,
  and the figure is shown when there is enough of it.
