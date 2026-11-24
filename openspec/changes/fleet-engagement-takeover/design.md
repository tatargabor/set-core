## Context

`fleet-mandate-and-desk` (open) gave a cross-project request a desk, an engagement record and
a quiet sweep. It reports a request open past the bound as *waiting* — a display state that
changes nothing. On 2026-11-24 two requests stopped for good while the screen said so
(`proposal.md`); both are re-measured in `measurements.md`. The owner's decision the same day:

- trigger on a stall — no movement and nothing working in the background — plus a hard ceiling;
  "whether it works in the background is visible anyway, not only from the transcript";
- the ladder is interrupt first, replace second;
- a takeover continues the predecessor's work from what is visible (OpenSpec state), it does not
  start over; live tests on running desks are allowed.

## Goals / Non-Goals

**Goals:**
- A request whose desk hangs or dies is moving again within about two stall bounds.
- A desk that is working — visibly or in the background — is never duplicated.
- The bus shows that a request changed hands, without waking anyone.
- The three liveness defects that produced the measured failures are closed.

**Non-Goals:**
- No change inside `set-agent-comm`; the framework posts nothing on the bus itself.
- No takeover of work mandates, no resumed predecessor session (a resume reloads the whole
  context, which is what token efficiency argues against).
- No judgement of answer quality.

## Decisions

### D1 — Its own loop, 60 s, and it reads the inventory only when there is something to watch

The quiet sweep runs every 300 s; a 5-minute stall bound on that cadence acts after up to ten.
The takeover round runs every 60 s, but first reads only the engagement store: with no `open`
engagement it returns without building the inventory, so an idle machine pays one small file
read a minute. *Alternative:* fold it into the sweep and shorten the sweep — rejected, the sweep
builds the inventory every round whatever the state.

### D2 — "Working in the background" is CPU outside the agent's own process

Measured (M2): the hung desk's scope used ~26 ms/s of CPU, ~9 ms/s of it the agent process
itself drawing its spinner, the rest idle helper servers. A real tool run (a test suite, a
build) uses hundreds of ms/s. So the signal is: `usage_usec` of the scope's cgroup minus the
main process's own CPU, as a rate between two rounds, against a bound of 5 % of one core. The
agent's own process is excluded because its spinner burns CPU exactly when it hangs. The
previous sample lives in memory, keyed by unit; the first round for a unit — or any read
failure — is *unmeasured*, and then only movement decides (and the decision says so).

### D3 — The interrupt is Esc, then the line, then Enter, written through the owner

The owner already holds the desk's terminal and has a `write` method. Measured live (M1): Esc
ended the hung tool call at once (`[Request interrupted by user for tool use]` in the
transcript); the typed line followed by a separate CR started a new turn within seconds. Text
and CR are separate writes ~0.8 s apart, so the CR is not taken as part of a paste. The line is
fixed text plus the room and timestamp — no request content.

### D4 — Takeover stops first, then starts under the same label

The desk label is an enforced identity: the owner refuses a second agent under it. So the old
desk is stopped (and its mandate ended `replaced`) before the new start. The new desk is
started through the same resolver path as any desk, with a mandate that carries a `takeover`
object `{room, ts, asker, from_seat, from_session}`. The engagement's desk fields are re-pointed
and `handovers` incremented. A start that fails leaves the engagement `open`; the next round
tries again (bounded by D6).

### D5 — The handover notice is the new desk's own entry

`fleet-mandate-and-desk` D7: the framework never speaks for an agent. The notice is therefore
the new desk's first act, from its own seat, unaddressed — it costs no other session a wake-up.
It is not reply-linked, so engagement closure (a linked entry by the addressed project) cannot
mistake it for the answer. The cost: the notice is an instruction, not a constraint; the
engagement record and the map carry the handover regardless.

### D6 — Two takeovers per request, then waiting

A request that hangs every desk (an impossible ask, a broken project) would otherwise start a
desk every ten minutes forever. After `fleet_takeover_max` (2) the request stays open and
waiting, which is the state the map already marks.

### D7 — The defects

- **End on measured absence.** `end_missing` gets a `unit_alive(unit) -> Optional[bool]`
  measurement (`systemctl --user is-active`); `True` or `None` keeps the mandate. A listing that
  failed to see an agent is a gap, not a zero.
- **Re-adopt a live desk.** The join already returns the mandate a live process carries in its
  environment, even when the record says ended. When that is a desk mandate of the project ended
  as missing (`ended`), resolution re-opens it and resolves to the agent — being in the live
  listing is the measurement. A mandate ended by an act (`replaced`, `stopped`, …) is not
  revived, so a replaced desk that is still dying is never picked.
- **Keep an asking desk.** The sweep counts `resolving`/`open` engagements whose asker is the
  desk's seat; a positive count keeps it (`asking-open`).

## Risks / Trade-offs

- [An Esc lands while the desk is doing legitimate work after the ceiling] → only once per
  request, and the line asks for a linked status answer, which is what the asker needed anyway.
- [Stopping a desk that was about to answer] → the replace step requires one more stall bound
  of no movement after the interrupt; an answer in between closes the engagement first.
- [Background CPU from an unrelated helper above 5 %] → the desk is judged working and is not
  replaced; the hard ceiling still interrupts once.
- [The new desk does not post the notice] → the record and the map still show the handover.

## Migration Plan

Additive fields on the engagement and mandate records (missing = defaults). Deploy = restart the
dashboard service when no desk is mid-answer; the owner needs no restart (it already has `write`).
Rollback = revert; the extra fields are ignored by the old code.
