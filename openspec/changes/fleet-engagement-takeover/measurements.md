# Measurements — fleet-engagement-takeover

All on 2026-11-24, on the live fleet of one machine. Consumer projects are not named.

## M0 — The `desk-not-ready` failure, from the service and owner logs

- 07:39:35 the framework's own project desk is started (mandate A, pid P).
- 08:12:20.77 mandate A is ended with reason `ended` — the reason only `end_missing` writes —
  in the second before the dashboard service was stopped for a restart (08:12:21).
- 08:21:57 a new request: the resolver records mandate B, the owner answers `refused start:
  <project>-desk is already owned here`, mandate B is removed, the resolver waits for a live desk.
- 08:22:57 `desk of a project has no bus seat after 60 s (started=False)` → engagement failed
  `desk-not-ready`.
- 08:27:43 the owner stops and reaps pid P — the agent had run the whole time.

So: a listing ended a live agent's mandate; the label stayed held; the resolver could neither
start nor find a desk.

## M1 — A hung desk, and the interrupt that freed it

- A consumer desk's transcript ends at 08:10:30 with a Bash `tool_use` (`timeout 580 …`, tool
  timeout 620 s) and no `tool_result`. At 11:06 the scope's process list holds the agent, its
  MCP helpers and its own background `sac wait` — no process of that command.
- The dashboard listed the desk `working` with `last_movement_seconds` 2775 at 08:56.
- The terminal tail (64 KiB) was nothing but the spinner's redraw.
- 11:07:38 `OwnerClient().write(label, b"\x1b")` → within 4 s the transcript gained the
  interrupted tool result and `[Request interrupted by user for tool use]`.
- 11:08:01 the nudge line written, then `b"\r"` 0.8 s later → 11:08:06 the desk issued a new tool
  call re-running the same check with a shorter bound.

## M2 — Background CPU of a hung desk

Over 10 s on the hung desk's scope cgroup: `usage_usec` +258 ms, of which the agent's main
process (utime+stime from `/proc/<pid>/stat`) +90 ms. The remainder (~17 ms/s, 1.7 % of a core)
is idle helper servers. A running test suite or build is far above 5 %.

## M3 — The asker swept while waiting

The engagement held open behind the hung desk was asked by another project's desk, which the
quiet sweep stopped at 08:17:40 — the sweep counts engagements addressed TO a desk's project,
not those the desk itself asked.
