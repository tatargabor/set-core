## Why

A wave board says how far each item got, but not **who it is waiting on**. Asked for a briefing on
a 30-item board (2026-10-29), the open questions had to be pieced together from item notes, a README
table and bus messages. The user asked for "which item needs a decision, where is the blocker" to
become part of the board standard. The same request: the status pills must not hang out of their
column. A 96px column let "in progress" overflow its pill on every in-progress row.

## What Changes

- **Waits on items.** An item MAY carry `waits`: a list of `{kind, who, text, ref}`, where `kind` is
  `decision` (a person has to choose) or `blocker` (work or access someone else has to provide).
  CLI: `wait <job> <item> (--decision|--blocker) TEXT [--who NAME] [--ref ID]` and
  `unwait <job> <item> [--ref ID | --all]`. The same ref replaces in place. A wait never changes
  the status.
- **The page lists them.** A "Waiting on people" panel at the top groups every open wait by person,
  decisions first. The summary gains decision/blocker counts, and each row and Kanban card shows
  its own waits. Skipped items are left out, done ones are not: a delivered item can still wait on
  a choice.
- **Pills fit.** The Waves list sizes its status column by the widest pill (subgrid, with a fallback
  where subgrid is missing), so no label overflows and the rows still line up.
- The skill documents waits and asks to read them first when reporting on a board.
