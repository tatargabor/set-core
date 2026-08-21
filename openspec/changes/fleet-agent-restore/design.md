## Context

The fleet screen's agent list is **discovered**, not stored. `fleet/discovery.py` reads
identity from `/proc/<pid>/comm`, the project from `/proc/<pid>/cwd`, and joins the
runtime's per-session record at `~/.claude/sessions/<pid>.json` to get the session id and
transcript path. Every one of those inputs is destroyed by a reboot, so after one the screen
is honestly empty — and the user has lost the composition of their working session.

**Three measurements taken 2026-08-21 on this machine shape the design, and each one closes
off an option that looks obvious:**

1. **`~/.claude/sessions` is not a history.** 50 files, 25 `.json` + 25 `.key`, **25 records
   against 25 live pids, zero stale** — the runtime removes a record when its session exits.
   So a post-reboot read of that directory cannot be relied on to describe what was running,
   and the filename is a **pid**, which is reused. Any record we depend on must be ours and
   must be keyed on the session id.
2. **The transcript survives and is the resume unit.** `discovery._session_log_for()` already
   resolves `~/.claude/projects/*/<sessionId>.jsonl`, with a comment recording that the
   tempting fallback — "the newest log in this project" — measured **4 correct of 9** and
   fails by giving confident wrong answers. We reuse that resolver rather than writing a
   second one.
3. **The resume machinery exists and is careful; only a route is missing.**
   `fleet/owner.py:recover()` stops the old scope, **re-reads** rather than trusting `stop()`'s
   return, refuses if the scope is not gone, and refuses outright if the session is bound to a
   live process — each guard carrying the reason that a resume against a live session forks its
   conversation silently. `OwnerClient.recover()` exposes it over the owner socket.
   `POST /api/fleet/agents` deliberately takes no `argv`, so there is no HTTP path to it today.

Constraints from the project's rules, all binding here: `lib/set_orch` stays domain-free; the
owner service stays thin, because **every restart of it kills every agent it holds**; nothing
derived from a consumer's domain may be persisted; the product is written in English; and a
UI change is not done until somebody has looked at the screen in a browser.

## Goals / Non-Goals

**Goals:**

- A durable, per-project record of the agents the fleet has seen, written while they are live.
- Reading it back when nothing it describes is running — the reboot case.
- One act, per project, that brings the whole recorded list back by resuming each session.
- An outcome per entry, with its reason, so a partial restore cannot read as a complete one.
- Keeping the existing refusal to resume a live session, rather than routing around it.

**Non-Goals:**

- Per-entry selection at restore time. The user asked for the list back; a subset restore is a
  different act and can be added later without changing this one.
- Automatic restore on boot or on page load. The act is chosen by a person.
- Reattaching to a surviving terminal. `owner.recover()`'s own docstring records the
  measurement (2026-08-17) that a pty master cannot be reacquired: `/proc/<pid>/fd/<n>` points
  at `/dev/ptmx` and opening it allocates a *new* pair. What survives is the transcript.
- Cross-machine sync of the record.
- Anything that deploys, promotes or releases as a consequence of restoring.

## Decisions

### D1 — The record is ours, written by us, keyed on the session id

**Decision.** A new module `lib/set_orch/fleet/roster.py` owns a durable document under the
framework's existing per-user store, alongside the arrangement:
`$XDG_DATA_HOME/set-core/fleet-roster.json` (mirroring `layout.default_layout_path()`, which
resolves `XDG_DATA_HOME` with a `~/.local/share` fallback). Keyed **project → session id →
entry**; each entry holds `label`, `cwd`, `kind`, `first_seen`, `last_seen`.

**Why not the runtime's own records.** Measurement 1: they are cleaned up on exit and keyed on
a reused pid. A record we do not own cannot be relied on for the one moment this feature is
about.

**Why not infer from the transcripts.** `~/.claude/projects/<slug>/*.jsonl` survives, but it
answers "what ever existed in this project", not "what was loaded". The user's own framing was
*the previous agent list*; a directory listing is a different, longer, noisier set — and it
cannot distinguish a session someone had open from one abandoned three weeks ago. The user
chose the snapshot over inference explicitly.

**Why the session id as the key.** A pid is reused; a label is chosen by the framework and can
repeat; the session id is what `--resume` takes. Keying on anything else would make the record
either duplicate entries or resume the wrong conversation — the second being much worse.

### D2 — Written from discovery's answer, not by a second scan

**Decision.** `discovery.list_agents()`'s **caller** hands the answer to `roster.record()`.
Discovery's return value and signature are unchanged, and discovery does not import the roster.

**Why the caller and not inside discovery.** Discovery is a read of process state; making it
write to disk gives a query a side effect, and would fire on every internal call including
those made from tests. The API layer already has exactly one place where a full discovery
answer exists per request.

**Why not a background sweep.** A second scanner is a second definition of "who is running",
and the two drift. The rule this repo keeps rediscovering: a copy of a definition drifts at
the moment it is written.

**Failure direction.** A write failure is logged at WARNING and swallowed *with respect to
discovery's answer* — the screen must not go blank because a record could not be saved. That
is the one place a swallow is correct here, and it is stated in the spec.

### D3 — Recording writes identity only, and one-shots are not recorded

`session_id`, `label`, `cwd`, `project`, `kind`, timestamps. No transcript content, no message
text, no tool output. This is the confidentiality boundary the project states: set-core may
*read* a consumer's data at runtime but must persist nothing derived from it. A `cwd` and a
project name are identity, not domain.

`kind == "oneshot"` (a `-p`/`--print` subprocess) is not recorded: finding CB-8 already
established these are the framework's own short-lived children, not sessions anyone is sitting
at. Restoring one would resume a subprocess as if it were a person's conversation.

### D4 — Resumability is computed at READ time, never stored

**Decision.** The stored entry does not carry `resumable`. Reading the roster resolves the
transcript through `discovery._session_log_for()` **at the moment of the read** and reports
`resumable` plus, when false, a reason.

**Why.** A stored boolean is a declaration about a moment that has passed — the same defect
this codebase already documents about the runtime's `status` field, measured at a median of
11 hours stale. Transcripts get deleted; a stored `true` would send restore at a session that
is not there.

**And an unresumable entry is returned, not filtered out.** A shortened list reads as a
complete one — the "false absence" class. The user must see that an agent they had is gone,
which is exactly the information a filter would destroy.

### D5 — Restore is its own module and its own route; the owner stays thin

**Decision.** `lib/set_orch/fleet/restore.py` holds the per-entry decision logic. It calls
`OwnerClient.recover(unit=…, session_id=…, cwd=…, label=…)` per entry. `owner.py` and
`ownerd.py` are not modified.

**Why not in the owner service.** Its own module docstring is the argument: *"a line of
business logic added here is a future outage of every running agent"*, because the owner's
lifetime is the agents' lifetime and every restart of it kills them all. Restore logic will
change; the owner must not have to restart when it does.

**Why not a parameter on `POST /api/fleet/agents`.** That body deliberately excludes `argv`,
with the recorded reason that an HTTP route running an arbitrary command list is a different
thing from a button that starts an agent. Restore is a third kind of start and gets its own
route: `POST /api/fleet/roster/{project}/restore`, with `GET /api/fleet/roster/{project}` to
read the list beforehand.

**Argv.** Restore does not accept an argv from the client. It passes none, so `recover()` uses
its own default (`claude --dangerously-skip-permissions --resume <sessionId>`) — the same argv
`ownerd.py` already documents must not drift from the interactive default.

### D6 — The live-session refusal is reused, and indeterminate counts as live

**Decision.** Restore does not re-implement the liveness check. It asks the same question
`owner._refuse_if_the_session_is_running()` asks, and treats a refusal as `skipped`, not
`failed`. Where liveness cannot be determined, the entry is **skipped** — matching that
function's existing behaviour, which raises rather than proceeding when it cannot tell.

**Why skipped and not failed.** They are read differently: `failed` invites a retry, and a
retry against a live session is precisely the fork the guard exists to prevent.

**Why not "stop it and resume it".** `recover()` does that deliberately for an *orphaned*
agent whose owner died. An agent that is running fine is not orphaned, and stopping a working
session to restore it would destroy the thing being restored.

### D7 — The result is per entry, and the screen shows it that way

The route returns `{"attempted": N, "started": [...], "skipped": [...], "failed": [...]}` with
a reason on every non-started entry. The screen renders the reasons where the reader is
standing.

**Why this is a decision and not a detail.** The rule the UI must not break: *compacting must
never hide a failure*. A restore of 9 that starts 3 is a partial result, and the single most
likely defect here is a green "Restored" toast over six entries that never came back.

### D8 — Retention is bounded, and pruning is reported

An entry unseen for longer than a retention bound (default 30 days, one constant, stated in
the module) is pruned on write, logged with session id and age. Without a bound the roster
grows without limit and a restore attempts sessions from months ago; with a silent one, an
entry disappears and looks like it was never recorded.

### D9 — Atomic write, no lock

Write via `tempfile` + `os.replace` in the same directory, as `layout.py` already does. There
is no version/conflict guard like the layout's, because the roster is not concurrently edited
by users — it is written by the API process from discovery and pruned there. A last-writer-wins
document is correct for an observation log; a conflict guard would be ceremony with nothing
behind it.

## Risks / Trade-offs

- **[A restore forks a live conversation]** → The guard already in `owner.recover()` is kept and
  not bypassed; indeterminate liveness is treated as live (D6). This is the highest-cost failure
  in the change: two sessions appending to one transcript, neither aware of the other.
- **[A partial restore reads as complete]** → Per-entry outcomes with reasons, counts of all three
  classes, and no single-message success (D7). Tested against a mixed result, not just a clean one.
- **[The roster grows stale and restore starts long-dead sessions]** → Retention bound with logged
  pruning (D8), plus `last_seen` shown per entry so the reader can see the age before acting.
- **[Restore starts many agents at once]** → Each start is a transient scope and a pty; a project
  with a dozen entries starts a dozen processes. The count is stated before the act, and the
  bounded set is exactly what the user asked to bring back. No parallelism beyond what the owner
  already does; entries are attempted in order and one failure does not abandon the rest.
- **[Discovery gains a write path]** → The write is at the call site, is exception-swallowing with
  respect to discovery's answer, and is covered by a test asserting discovery's result is
  unchanged when the store is unwritable (D2).
- **[A `cwd` in the roster no longer exists]** → Treated as a skip with a reason naming the missing
  directory, the same class as a missing transcript. Not a failure, and not silently dropped.
- **[The record is a new persisted file — confidentiality]** → Identity only, enumerated in D3 and
  asserted by a test that writes an entry from a session whose transcript contains message text
  and greps the stored file for it.

## Migration Plan

No migration. The roster file does not exist yet; its absence reads as an empty record, which
is the specified behaviour for a project never seen. Rollback is removing the routes and the
file — nothing else reads it, and discovery is unchanged.

The first population happens naturally: once shipped, the next discovery call records what is
live. **A roster written before this ships does not exist, so the first reboot after deploying
is the first one that can be restored from** — worth saying out loud so the feature is not
judged broken on the reboot it could not have covered.

## Open Questions

- **Label collision on restore.** The owner refuses a label already held. Restore proposes the
  recorded label and, on refusal, must either derive a fresh one or report the entry as skipped.
  Deriving is preferred (the user asked for the agents back, not for their names), and the chosen
  label is reported in the outcome. To be settled in implementation against the owner's actual
  refusal behaviour, measured rather than assumed.
- **Whether the roster should record agents the fleet did not start (`foreign`).** Current answer:
  yes — the user's list included them, and the record is of what was *loaded*, not of what the
  framework owns. Restoring one starts a framework-owned agent on a foreign session's transcript,
  which is the same act `recover()` already performs for an orphan.
