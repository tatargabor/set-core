## Why

An agent compacts without warning. Nothing on the fleet screen says how full a session's
context is, so the first sign is the compact itself — after the precision is already gone.

This became a different problem the moment the machine gained a third provider. The windows
are no longer one size: **272 000** (gpt-6-astra), **900 000** (glm), **200 000** and its 1M
variants (anthropic). A bare token count therefore carries no meaning without the window it is
measured against — 230 000 tokens is a healthy quarter of a GLM session and past the end of an
Astra one. The provider that fills fastest is the newest and least familiar, which is exactly
the one a reader has no intuition for.

The measurement already exists and is thrown away: the fleet agent payload carries
`cache.tokens` and `cache.model` per agent today, and nothing renders the fraction.

## What Changes

- The fleet header gains **one context-fill mark per LIVE agent**, beside the account quota
  bars it already carries, each drawn against **its own model's window**.
- The window is resolved from the **measured** `cache.model`, never from the recorded
  provider. Measured on the running dashboard: a live agent carried
  `provider: {"recorded": false}` while its `cache.model` was present — resolving from the
  record would have left every unrecorded agent with no bar at all, which reads as an agent
  consuming nothing.
- A model whose window is **not known** renders as the strip's existing unmeasured `?` mark —
  never an empty or zero-width bar. Absent is not zero: an empty bar is the most confident and
  least true thing this mark could say.
- The number of bars is **capped**, with an overflow count for the remainder, so a large fleet
  cannot flood the header line. The cap SHALL NOT be able to hide a filling agent: the agents
  shown are chosen by fullness, so anything hidden is emptier than everything visible.
- `cache.tokens` is stated as a **proxy** for context size, in the mark's own description —
  it is the cache read plus cache creation of the last request, not a context measurement the
  runtime published. The screen must not imply a precision nobody measured.

### Why this does not contradict `fleet-usage-bars`

That capability forbids attaching a consumption mark to an agent tab or tile, and the reason is
a measurement: account quota has no per-seat identity to join on — 4 of 40 transcripts carried an
owning account, so a per-tab quota mark would render 36 agents as consuming nothing.

**Context inverts every term of that argument.** It is read from the agent's *own* transcript,
so it needs no join and has no attribution gap; it is a per-agent fact in the way quota is not.
The two remain separate measurements with separate marks, which is the same separation
`fleet-usage-bars` already draws against cache heat.

## Capabilities

### New Capabilities
- `fleet-context-fill`: how full each live agent's context window is — resolving a window from
  the measured model, drawing the fill per agent on the fleet header, and what the mark must say
  when the window is unknown or the fleet is larger than the header can hold.

### Modified Capabilities
<!-- None. `fleet-usage-bars` keeps its requirements unchanged: its per-tab prohibition is
     about account quota, a different measurement, and this change adds no mark to a tab or
     tile. `context-window-metrics` is a different surface (the change list, from
     `loop-state.json`) and keeps its own 200 000 constant; this change does not touch it. -->

## Impact

- **Web** — a new mark in the fleet header line beside `FleetUsageStrip`, and a new
  `web/src/lib/` module holding the fill decisions as pure functions so each is assertable in
  both directions, matching `fleetUsageBars.ts` and `fleetCacheHeat.ts`.
- **Python** — the per-agent window and fill computed server-side in the fleet payload
  (`lib/set_orch/fleet/`), so the browser never re-derives a figure the server already states;
  the same rule `cache_heat.py` follows for `cooled`/`cold`.
- **No new upstream call, no new credential, no new poller.** Both inputs are already in the
  payload the fleet screen fetches.
- **Not touched**: account quota measurement, the cache-heat marks, the Control Center strip,
  and `context-window-metrics`' change-list surface.
