## Context

The roster is a document. It consults nothing live at read time — that is deliberate and
stated in `read()`'s own docstring — so everything it can ever say is decided at *write*
time, by `record()`. Two facts that exist at write time are not reaching it, and the result
is a record whose majority is noise it generated itself.

Measured on this machine, 2026-08-27, `set-fleet-roster`: **8 entries, 6 un-restorable, 4 of
them `no-session:` keys.** Three of those four are the same live session under successive
pids, and that session has a runtime record — so the reason printed beside them,
*"no session id was ever recorded for this agent"*, is false about the fleet and false about
the framework's own knowledge.

Two write-time facts are being discarded:

| fact | where it exists | where it is dropped |
|---|---|---|
| the session the framework started an agent on | `OwnerClient().list_agents()` → `resumed_session` | `api/fleet.py::_record_roster`, which forwards only `labels` |
| that a `no-session:` entry's agent is no longer observed | the sweep that writes the round | `_prune`, which knows only age |

The second is the larger one and was not in the report. It is a per-agent leak: every agent
discovered before the runtime writes its per-pid record gets a `no-session:` entry, then a
second entry under its real session id, and the first is never retired.

## Goals / Non-Goals

**Goals:**

- The roster records a session identity whenever *anybody* knows one — the runtime first,
  the framework's own start intent second.
- A `no-session:` entry lives only while it serves its one stated purpose, and no longer.
- Every reason line the reader sees is true of the entry it sits beside.
- `tests/unit/test_fleet_roster.py` and `tests/unit/test_fleet_persistence_boundary.py` keep
  passing **unedited**. An edit is a signal a contract moved.
- The stored document gains no new field, so an existing roster stays readable and no
  migration is needed.

**Non-Goals:**

- The race that produced the original report. `owner._refuse_if_the_session_is_running` was
  verified working the same day — it refused a second resume of a live session with the right
  message — and the window belongs to a human's terminal.
- The restore panel's contradictory header (B-87).
- Anything about `manager/cli.py`. Its `systemctl` calls are broken on both platforms because
  no `set-manager` unit exists anywhere in `templates/`; that is not a macOS-transition item
  and carrying it here would hide it rather than fix it.
- Consulting live state at read time. `read()` answers after a reboot, when nothing is live.

## Decisions

### D1 — The framework's start intent is a SECOND source, never a replacement

`_entry_from` keeps taking `agent.session_id` first. Only when that is absent does it fall
back to what the framework recorded at the moment of starting.

The order matters and is not arbitrary. The runtime's record is what the *process* is bound to
now; the framework's is what it was *asked* to resume. They can disagree — an agent that was
told to resume `<S>` and could not claim it is exactly the case that produced this report — and
when they do, the process's own answer is the one a reader is asking about. So the framework's
answer fills a silence; it never overrides a statement.

*Alternative considered:* prefer the framework's answer for framework-started agents, on the
grounds that it is more authoritative about intent. Rejected — the roster answers "what was
open", not "what was requested", and preferring intent would let a failed resume overwrite a
successful one under the same pid.

### D2 — It travels as a pid-keyed mapping, beside `labels`, from the same answer

`record(..., labels=..., sessions=...)`, where `sessions` is `pid → session id`.

Same shape as `labels`, derived from the same `OwnerClient().list_agents()` call the API
already makes for `owned`, so there is no second round trip and no new failure mode. The
tri-state is preserved verbatim from `_owned_by_pid`'s own docstring: `None` means the owner
could not be asked, `{}` means it answered and holds nothing. Collapsing them would make an
unreachable owner indistinguishable from an owner holding nothing — and the second is a
statement, the first is a gap.

*Alternative considered:* have `roster.py` ask the owner itself. Rejected on the module's own
stated rule — it is a document, and *"a document that opens a socket to the agent owner would
make every write depend on a service being up"*.

### D3 — A `no-session:` entry's lifetime is the sighting, not the retention window

The retention bound exists so that an entry somebody could still act on survives a machine
being off. A `no-session:` entry can never be acted on: there is no session id, so there is
nothing to resume, and `read()` already says so. Its only stated purpose — from the constant's
own comment — is to stop the roster claiming a smaller fleet than exists *while the agent is
live and unknown to the runtime*.

So: **a full sweep removes every `no-session:` entry it did not see this round.**

Note the fail direction, because it is what makes this safe. Nothing that could have been
acted on is lost — the entries removed are exactly the ones `read()` reports as un-restorable
with no session id. And the key is deterministic, so an agent still around reappears on the
next sighting. The failure mode of the *current* behaviour is the reverse and worse: a record
that grows by one dead entry per agent and presents them as fleet history.

**A partial write must not do this**, and `record()` already carries the distinction it needs.
`full_sweep=False` means "`agents` is not the whole fleet", and a partial caller removing
entries it simply did not look at would delete live agents' rows. The existing `last_round_at`
stamp is guarded by exactly this flag for exactly this reason; the same guard, the same
argument.

*Alternative considered:* a shorter retention for `no-session:` keys — an hour, a day.
Rejected: it turns a correctness property into a timing question, and a machine asleep for two
hours would then look like one whose agents all died.

### D4 — The reason line is derived from the entry, so it cannot outlive the fact

`read()` composes three cases today. With D1 in place, a framework-started agent has a real
session id, so it falls into the transcript branch and the false *"no session id was ever
recorded"* line stops appearing for it — no special case is needed.

What remains is that the surviving no-session case must say something a reader can act on. It
is not "nothing was recorded"; it is "nobody knows one" — the runtime has not written a record
and the framework did not start this agent. Written that way, the line tells the reader which
two sources were asked.

### D5 — The docstring is corrected and the behaviour is held in a test

`_no_session_key` claims to be "stable across sightings … never from its pid". Measured false
on both counts: with no name it returns `pid-N`, and the key changes the moment the runtime
supplies a name, so one agent can leave more than one orphan.

The docstring says what the function does. The pid fallback and the key's instability across a
naming event go into a test — prose describing behaviour is the carrier that decays silently,
and this repo has paid for that shape before.

## Risks / Trade-offs

- **A sweep that fails to see a live, runtime-unknown agent now deletes its row.** → The row
  is un-restorable, so nothing actionable is lost, and it returns on the next sighting. Stated
  rather than defended away: this trade is only acceptable *because* the entry can never be
  acted on, and it would be wrong for any entry that can.

- **`sessions` is one more thing a caller can forget to pass.** → It defaults to `None`, which
  means "not asked", and the behaviour is then exactly today's. The API is the single caller
  and passes it from an answer it already holds.

- **A framework-started agent whose real session already has an entry now merges into it.**
  Two processes, one session, one row — which is the roster's own identity rule applied
  consistently. The visible consequence is that the row can gain the framework's label for the
  losing process. That is a true fact about the session (the framework does hold a process on
  it under that name), and it is preferable to a second row that can never be restored. Called
  out here so it is a decision on the record rather than a surprise in a diff.

- **The orphans already on disk.** → No migration and no cleanup script. The first full sweep
  that does not see their agents removes them, which is the same code path this change adds
  and therefore the same thing being tested.

## Migration Plan

None required — no stored field changes shape. Verification order, because the later steps
cannot be trusted until the earlier ones hold:

1. `test_fleet_roster.py` and `test_fleet_persistence_boundary.py` pass **unedited** — proves
   nothing existing moved.
2. A unit test drives a full sweep that does not see a `no-session:` entry and asserts it is
   gone; a partial write with the same input asserts it is kept.
3. On this machine: after a listing round, `set-fleet-roster` shows no `no-session:` entry for
   a pid that has a runtime record or that the framework started, and none for a process that
   is gone.
4. The fleet screen is opened in a browser and the restore panel is looked at.

## Open Questions

- Whether `read()`'s no-session reason should also name the two sources it consulted
  ("the runtime has no record and the framework did not start it") or stay short. Decided
  during implementation and recorded in `tasks.md` either way — a reason line is the thing a
  reader acts on, so the wording is a decision, not a detail.
