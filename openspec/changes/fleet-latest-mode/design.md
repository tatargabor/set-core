## Context

The fleet screen has two panels: projects on the left, the selected project's agents on the
right. Everything on the right is derived from one value — `active`, the selected project — and
its per-browser view memory (`fleetViewState.ts`) is keyed by that project's name: columns,
enlarged tile, open terminals, open logs. PM mode already crosses projects, but only for one agent
at a time, and it does so by *selecting* that agent's project (`presentAgent` in `Fleet.tsx`).

The ordering signal exists: `GET /api/fleet/agents` returns every agent of every project in one
answer, and each carries `last_human_input_seconds`, measured by `_last_human_input` in
`lib/set_orch/fleet/state.py` from the newest `user` entry with text in the session transcript,
tool results excluded, age taken from the entry's own timestamp.

Measured on the live fleet 2026-10-19: 19 agents across 14 projects, and the value was absent for
6 of them, one of which was working at that moment. The cause is structural: the measurement reads
the last 256 KB (`TAIL_BYTES`), and a long tool run fills that with tool traffic.

## Goals / Non-Goals

**Goals:**
- One screen with the agents the reader is currently working with, regardless of project.
- No tile moves under the reader's hand.
- The ordering signal is present for every agent that has a human message anywhere in its
  transcript.

**Non-Goals:**
- A server-side mode. The mode is a way of looking, held in the browser like the rest of the
  view state; the server learns nothing new except a better-measured field.
- Ranking by agent activity or wait time. That is PM mode's question, not this one.

## Decisions

### D1. The mode is a virtual project, not a second screen

While on, `active` is replaced by a synthetic project whose agents are the selected N, and the
view memory uses a reserved key (`latest/`) instead of a project name. Everything downstream —
the grid, the enlarged view, the tab strip, the column choice and `fitColumns` — runs unchanged.

*Alternative considered:* a separate component that renders its own grid. Rejected for the same
reason PM mode's first build was rejected (see `fleet-pm-mode`): a parallel surface loses every
affordance the real one has, and the two drift.

*Why the reserved key cannot collide:* project names come from discovery and are directory names;
the key contains a `/`, which no directory name can (the first sketch said `__latest__`, which is a
legal directory name and was therefore not used), and `fleetViewState` refuses to treat
it as a project anywhere else.

### D2. Every tile takes its OWN agent's project

Tiles today receive `projectRoot`, `knownFiles` and the docked-edge lookup from `active`. In a
virtual project those would be wrong for every tile but the ones whose agent happens to belong to
the last selected project — and wrong *silently*: a file link would open a path in another
project's tree. So the tile receives its project from the agent (`agent.project` → that project's
root from the same `/api/fleet/agents` answer), and the synthetic `active` carries no root at all,
so anything still reading `active.root` fails loudly in test rather than resolving against a
wrong tree.

This is the main implementation risk, and it is why the spec has a scenario for it.

### D3. A poll patches in place; a switch re-ranks

**Decided by the user on 2026-10-23, in two steps on the same day.** First the stable slots below were
reversed (*"latest tabok kellene frissüljenek nem csak amikor megnyitom, most a sorrend mindig az ahogy
megnyílt először"*) into a re-rank on every poll, held while the pointer was over the strip or the
grid. In use that jumped at moments unrelated to anything the reader did — on the pointer leaving
the strip, and whenever anyone wrote into any agent — and the user called it odd (*"néha ugrik de
fura"*). Offered three options (re-rank on switch, animated live, live without the hold), they chose
**re-rank on switch**.

```
initial(agents, n)            → the n most recent (measured first, unmeasured last)
update(slots, agents, n)      → on a poll: same slots; departed agents free their slot; an agent
                                now within the top n takes a free slot, or else the slot of the
                                slotted agent with the oldest recency. Same array when unchanged.
on a switch of the enlarged agent → initial(agents, n)
```

The order changes where the reader acted, so it reads as a consequence, alt-tab style: the agent
just left — the one just written into — comes to the front. The click has landed by then, so no
pointer hold is needed, and none is kept. The re-sort control is gone; the switch is the re-sort.

*Known limit:* the re-rank uses the last poll's recency (about 5 s). Typing into an agent and switching
away within that window ranks it by its previous message.

*Rejected:* re-ranking on every poll (with or without a pointer hold) — the moves are not tied to the
reader's own act. Animating the moves — the motion would still arrive at unrelated moments.

### D4. Mutual exclusion with PM mode lives in the page, not the server

PM mode's `enabled` is owned by the server; latest mode is browser state. Turning latest mode on
posts `enabled: false` to `/api/fleet/pm` (the existing toggle path); turning PM mode on clears
latest mode. The PM toggle already reads its state back from the server on load, so a PM mode
turned on elsewhere is seen and latest mode yields to it.

### D5. The deep human-input search: backwards in chunks, cached by growth

When `_last_human_input` finds no human entry in the tail, a second function reads the transcript
backwards in `TAIL_BYTES` chunks until it finds one or reaches the start. The result is cached in
memory as `{path: (inode, size_searched, epoch_of_human_entry | None)}`.

On the next poll:
- same inode and the file has only grown, and the tail search again found nothing → the new bytes
  are all inside the tail that was just read, so the cached epoch is still the newest → reuse it,
  and the age is recomputed from `now`;
- the tail found a human entry → the tail wins and the cache entry is refreshed;
- the inode changed or the file shrank → the entry is dropped and the search runs again.

If the bytes appended since the cached search exceed the tail, the gap between `size_searched` and
the tail's start is read once, so no region goes unread.

The cache holds only a timestamp per path — never message text — and lives in process memory,
consistent with the persistence boundary in `CLAUDE.md`. It is bounded by the number of live
transcripts, and entries for transcripts no longer listed are dropped on each listing.

*Alternative considered:* a `UserPromptSubmit` hook that writes a timestamp. Rejected: it would
measure only sessions that have the hook installed, and the fleet deliberately measures from the
transcript so that every session counts the moment it exists.

*Alternative considered:* raising `TAIL_BYTES`. Rejected: it moves the wall rather than removing it,
and it multiplies the cost of every other measurement that shares the tail.

## Risks / Trade-offs

- [A cold start reads whole transcripts] → only for agents whose tail holds no human entry, in
  chunks, once per transcript; logged at DEBUG with bytes read, at WARNING if one search exceeds
  a size worth noticing.
- [Ten tiles from ten projects] → tiles mount a terminal only when one is opened, so the default
  cost is ten summary cards; the enlarged view plus the tab strip is the expected use.
- [The mode hides projects that need attention] → the project column stays visible with its
  awaiting and attention markers; only its *selection* is cleared.
- [A tile reads `active.root` somewhere unnoticed] → D2 gives the synthetic project no root, and a
  test drives a file link from a tile of a project that is not the last selected one.

## Migration Plan

None. The API field keeps its name and meaning; `null` merely becomes rarer. The view memory gains
one reserved key; an older build ignores it.

## Open Questions

- None blocking. Whether the count control should also offer "all agents" is left to use: the
  number control accepts any value up to the number of agents.
