## Context

The roster is a 30-day accumulating record keyed on session id, and restore attempts every
entry it holds for a project. Because a `--resume` mints a new session id, one named agent
accumulates one entry per resume, so the record grows far past the composition it was meant
to bring back — measured on one machine: 233 recorded entries against 13 that were open in
the last discovery round, with a single label holding five recorded session ids.

Two properties of the existing design are what make the fix cheap, and both must survive it:

- `roster.record()` is called once per discovery pass, from the one route that already holds
  a full discovery answer, and stamps the **same** `now` on every entry that pass saw.
- `roster.read()` deliberately consults nothing a reboot destroys. Whatever "was open" means
  here, it must be derivable from the document alone.

## Goals / Non-Goals

**Goals:**

- Offer back the composition the user had, with the rest of the record still reachable.
- Let restore be asked for an explicit subset, without changing what the bodiless call means.
- Keep every "we could not determine this" distinguishable from "this is false".

**Non-Goals:**

- Deduplicating the record. Five session ids under one label is *correct* — they are five
  different conversations. The defect is which of them gets offered, not that they exist.
- Restoring the panel/tab arrangement. That already lives in `fleetViewState` (per browser,
  by label) and is re-applied when the agents are back; it is a different lifetime.
- Any automatic restore. Restore stays an act somebody takes.

## Decisions

### The round is a stamp on the document, not a time window over entries

`record()` writes `last_round_at = now` at document level, and "in the last round" is
`entry.last_seen == last_round_at` — exact equality, because the same float is written to
both in the same call.

*Alternative considered: derive it at read time as `max(last_seen)` across the document.* It
needs no schema change and is self-repairing, and it is wrong in the one case that matters: a
machine that went down with **nothing** running has a max that points at the last time
something was alive, so the surface would present a composition from days earlier as the one
that was open. That is the false-value class, in the acting direction. The stamp answers
"when was the fleet last observed", which is the question, and the max answers "when was
something last alive", which is not.

*Corollary — the stamp is written even by a round that saw nothing.* That is the whole point
of preferring it, so it must not be skipped as an optimisation.

### A partial record write must never move the stamp

Today there is exactly one caller and it always passes the full fleet (`GET
/api/fleet/agents` has no project filter). That is a property of the current code, not a
guarantee, and if a future caller records a subset the stamp would advance while most entries
kept an older `last_seen` — every one of them then falls out of the composition. The fail
direction is safe (offering too few, never too many), but it is silent, so `record()` takes an
explicit `full_sweep: bool = True` and only stamps when it is true. A partial caller has to
say so, and gets a documented no-stamp instead of a quietly wrong one.

### Absent, empty and unknown are three values, and each is carried as one

- `last_round_at` absent → every entry's `in_last_round` is `None`, never `False`. The surface
  falls back to the whole list *and says why*.
- A selection absent (`None`) → the whole record, unchanged behaviour.
- A selection present but empty (`[]`) → nothing is attempted. The tempting `keys or entries`
  fallback would turn "restore none" into "restore all nine", which is precisely the act this
  change exists to prevent.

### An unrecognised key is an outcome, not a filter miss

Filtering the entry list by a set of keys makes an unknown key disappear, and the result then
reports fewer attempts than were asked for while reading like a complete one — a filter
downstream of a source undoing it. So the selection is iterated, not the entries: each
requested key that the record does not hold produces a `skipped` outcome carrying that
reason, and it counts in `attempted`, so `complete` goes false.

### The surface keeps one restore act and two offers

`FleetRestore` grows a second, secondary offer rather than a second mechanism: the primary
button posts the composition's keys, the expander lists the remainder with checkboxes and
posts the checked ones. Both go through the same route and the same `summarise()`, so the
partial-result rendering that already exists cannot drift into two versions.

The composition's age is stated on the control itself (`ageLabel`, already shared with the
tile), because a three-day-old composition and a thirty-second-old one deserve different
confidence, and the control is where the reader is standing.

### The arming stays

The existing confirm-before-act (`armed`) is kept for both offers. It was added after a
mis-aimed click started 21 agents, and a smaller default set is a reason to keep the guard
proportionate, not to drop it.

## Risks / Trade-offs

- **A fleet observed while the user had already closed things reports a composition smaller
  than they remember.** → That is the honest reading of what was open, and the remainder is
  one click away with its own count, so nothing is hidden.
- **The dashboard being down before a reboot makes the last round older than the crash.** →
  The observation's age is stated on the control, which is exactly the case it is there for.
- **A stored roster from before this change has no stamp.** → Read as unknown, whole-list
  fallback, stated on screen. No migration, no rewrite of an existing document.
- **`in_last_round` is derived at read time from a stored float comparison.** → Equality on a
  float written by the same call is exact; nothing rounds it in transit because the write and
  the read both go through JSON as a number. Held by a test that records two rounds and
  asserts membership rather than by inspection.

## Migration Plan

No migration. The stamp appears on the next `record()` write, which happens on the next fleet
poll; until then the surface reports the composition as undeterminable and offers the whole
list, which is today's behaviour with an honest label on it.

## Open Questions

None blocking. One deliberately deferred: whether the roster should also collapse the
per-resume duplicates into a lineage per label. It would shrink the remainder list, it is not
needed for the composition to be right, and it is a change to what the record *means* rather
than to what restore offers.
