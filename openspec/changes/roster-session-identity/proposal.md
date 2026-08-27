## Why

The fleet roster is manufacturing entries that can never be restored, and it is doing it at a
rate of one per agent. Measured on this machine on 2026-08-27 with `set-fleet-roster`:
**8 entries, 6 of them un-restorable, 4 of those keyed `no-session:`.** For one project:

```
3bf44330-…                      sess=3bf44330  run=True   RESUMABLE
no-session:<project>/pid-9289   sess=-  label=<restored>  "no session id was ever recorded for this agent"
3d0f3e55-…                      sess=3d0f3e55  label=<probe>  RESUMABLE
12cc214f-…                      sess=12cc214f  "no transcript on disk"
no-session:<project>/pid-9467   sess=-         "no session id was ever recorded for this agent"
no-session:<project>/pid-37343  sess=-         "no session id was ever recorded for this agent"
```

Two of those `no-session:` keys are the *same live session*, recorded under two of its
successive pids — and that session has a runtime record, so the reason printed beside them is
false. The roster's whole purpose is to answer "what was open, and what can be brought back";
three quarters of what it holds for this project is noise it generated itself.

This was found from a user report that a restore "did not work". The restore did work — what
did not work is what the roster wrote down afterwards.

## What Changes

**Defect 1 — the framework discards what it already knows.**
`roster._entry_from` takes the session id from `discovery`, which reads the runtime's per-pid
record. For an agent the *framework* started with `--resume <S>` whose runtime record never
appeared, that is `None`, so the roster writes `no-session:<project>/pid-N` and states
`"no session id was ever recorded for this agent"`. That statement is false. The owner records
the session at the moment of starting and already reports it — measured,
`OwnerClient().list_agents()` returns `"resumed_session": "<S>"` for exactly that pid. The
answer reaches `api/fleet.py::_record_roster` inside `owned` and is dropped there, because
`record()` accepts only `labels` (pid → label).

- `record()` gains the framework's own session knowledge, keyed by pid — the same shape and
  the same owner answer `labels` already travels in, so no second round trip.
- `_entry_from` uses it **only** when the runtime's record is silent. The runtime remains the
  first source; this is what the framework knows it *asked for*.
- `None` (the owner could not be asked) stays distinct from `{}` (it answered and holds
  nothing), exactly as `_owned_by_pid` already documents.

**Defect 2 — every agent leaves a permanent orphan, and this one is larger.**
`no-session:<project>/pid-9467` is a live session that *does* have a runtime record;
`pid-37343` is the same session under its previous pid. The entry is created in the window
between an agent being discovered and the runtime writing its record. When the record appears,
a second entry keyed by the real session id is added — and the `no-session:` one is never
retired. It survives `RETENTION_SECONDS` (30 days) as junk that can never be restored. Three of
this project's four are of this kind.

- A `no-session:` entry is un-restorable **by construction** — there is nothing to resume. Its
  only stated purpose is to keep the roster from claiming a smaller fleet than exists while an
  agent is live and unknown to the runtime. That purpose ends when the agent is no longer
  observed, so a **full sweep that does not see it removes it** rather than keeping it for a
  month.
- A **partial** write must not do this. `full_sweep` already carries exactly that distinction
  for `last_round_at`, and the same argument applies unchanged.

**Defect 3 — the key's docstring describes a function that does not exist.**
`_no_session_key` says it is "stable across sightings … derived from what does not change about
it (its project and its label), never from its pid". Measured: with no name it falls back to
`pid-N`, and the key *changes* the moment the runtime supplies a name — so one agent can leave
more than one orphan. The prose is corrected, and the pid fallback is held in a test rather
than in a sentence.

**And the reason text follows the fact.** An entry the framework started with a known session
must not be labelled "no session id was ever recorded for this agent".

## Capabilities

### New Capabilities

- `roster-session-identity`: where a recorded agent's session identity comes from — the
  runtime's record first, the framework's own start intent second — and what a reason line
  may claim when neither knows.
- `roster-entry-lifetime`: how long an entry lives, split by whether it can ever be acted on;
  and which kind of write is allowed to retire one.

### Modified Capabilities

None. No existing spec in `openspec/specs/` states requirements about the roster's key
construction or its retention split.

## Impact

- `lib/set_orch/fleet/roster.py` — `record()`, `_entry_from`, `_no_session_key`, `_prune`,
  and the `read()` path that composes `not_resumable_reason`.
- `lib/set_orch/api/fleet.py` — `_record_roster` passes the framework's session knowledge
  through, from the `owned` answer it already holds.
- `tests/unit/test_fleet_roster.py` — must keep passing **unedited**; an edit is a signal a
  contract moved, not a routine adjustment.
- `tests/unit/test_fleet_persistence_boundary.py` was named here as a second "unedited" suite
  and that was wrong on this platform: **two of its tests were already failing**, because its
  instrument loads `libc.so.6` and reads `/proc/self/fd` to count inotify watchers. The
  property they measure — the fleet read path allocates no file watchers, so its cost cannot
  grow with the agent count — is platform-independent; only the primitive is not. That
  instrument is ported to `kqueue` in a **separate commit**, because it changes no contract and
  belongs to the macOS transition rather than to the roster. Named here so the correction is on
  the record rather than discovered from a diff.
- The stored document gains no new field. Existing rosters stay readable, and the orphans
  already in them are removed by the first full sweep that does not see their agents.

**Explicitly out of scope, because the boundary is what keeps this honest:**

- The race behind the original report (B-86). The guard
  `owner._refuse_if_the_session_is_running` was verified working the same day — it refused a
  second resume of a live session with the right message. The window belongs to a human's
  terminal, not to the framework.
- B-87, the restore panel printing the current offer beside the last result.
- `manager/cli.py`'s unconditional `systemctl`. Measured broken on **both** platforms — no
  `set-manager` unit exists in `templates/systemd/` or `templates/launchd/` — so it is not a
  macOS-transition item and must not be carried in as one.

**macOS transition status, measured today rather than assumed**, because this change is the
last piece of it: all five fleet endpoints return 200; the shell layer already branches on
platform everywhere a GNU-only construct appears (`bin/set-common.sh` on `$PLATFORM`,
`lib/loop/state.sh` on `uname`, `lib/orchestration/utils.sh` on `command -v flock`, with
`flock`, `date -d` and `stat -c` all confirmed absent here); `owner_client` and `ownerd` were
ported by `macos-agent-owner`, and the process readers by `macos-fleet-discovery`. The roster
is the remaining measured gap.
