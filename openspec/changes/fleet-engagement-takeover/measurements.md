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

## M4 — The first live round (11:16, right after the service restart)

One open request, 12 minutes old, addressed to a consumer desk that had sat idle at its prompt
since 09:48 — the bus never woke it for the new request. The round decided `interrupt`
(`stalled (movement-only)`, moved 1824 s ago, CPU unmeasured). The line reached the desk, which
began working on the request within 30 s. The decision was right; its basis was not: on the
first round after a restart NO desk has a CPU sample, so a long test run that writes nothing to
the transcript would have been interrupted too. Fixed: a unit's first sample answers `pending`
and the stall decision waits one round (a gone desk still needs none).

## M5 — Both measured stopped requests closed after the interrupt (11:20)

- The request that sat three hours behind the hung desk (M1): `answered` after the hand-made
  interrupt of 11:07 — total age 11 677 s.
- The request the first automatic round interrupted (M4): `answered` at 864 s of age, i.e.
  within about four minutes of the interrupt. Its `nudged` flag is set and `handovers` is 0 —
  the cheapest step was enough, no desk was started.

## M6 — 4.3 FAILED on its first live run: a busy desk was interrupted (11:24)

The live test asked the framework's own desk to run a 420 s CPU loop, then `sleep 600`.
At 11:24:26, five minutes into the CPU loop (one core at 100 %, measured with `ps`), the round
decided `interrupt (stalled (movement-only); moved=305 cpu=unmeasured)`. The desk answered at
11:24:33 that step 1 was interrupted before it finished.

Cause: the sampler took the scope from the inventory row's `unit` field, and for a
framework-held agent that field is `None` (measured on the same row: `{'pid': 540200,
'unit': None, 'scope': None}`). Every round therefore read "unmeasured" and fell back to
movement — the exact case the CPU signal exists for. The unit tests passed because their rows
carried a `unit`: a test driving the thing with an input the live system does not produce.

Fix: the cgroup is read from the process itself (`/proc/<pid>/cgroup` → `cpu.stat`), keyed by
pid, no `systemctl` call. A test now drives the real readers with the live row shape (no unit,
this process's pid) and fails on the previous code.

## M7 — 4.3 and the interrupt half of 4.2 pass live (11:27-11:40, after the M6 fix)

Same request to the framework's own desk: a 420 s CPU loop, then `sleep 600`. A round every
45 s (plus the service's own every 60 s) logged each decision:

| time | moved (s) | background CPU | decision |
|---|---|---|---|
| 11:27:43 | 0 | pending (first sample) | none — cpu-sampling |
| 11:28:28 … 11:34:33 | 39 → 404 | 91 – 101 % | none — working (past the 300 s bound at 11:33:02 and 11:34:33) |
| 11:33:47 | 358 | pending | none — cpu-sampling: the service was restarted by another session at 11:33:14, so the sampler started fresh |
| 11:35:19 … 11:39:09 | 25 → 254 | 0.4 – 0.8 % | none — moving |
| 11:39:54 | 301.8 | 0.8 % | **interrupt — stalled (movement+cpu)** |
| 11:40:07 | — | — | engagement `answered` |

The desk's own report (reply linked to the request): the CPU loop ran its full 420 s
(11:27:48 → 11:34:48) without interruption; the sleep was interrupted by the `[fleet]` line and
nothing was re-run.

## M8 — The replace path live (11:41-11:44), and two defects it exposed

A request to the framework's own desk (`sleep 90`, then answer); the desk was stopped through
the fleet's stop route 28 s later (11:41:38).

- 11:42:36 the round decided `replace (desk-gone)`; 11:42:37 a desk was started; 11:42:42 the
  engagement was handed over (`handovers=1`) to the new seat.
- 11:43:38 the successor posted the unlinked handover FACT in the request's room.
- 11:43:57 it answered with a reply linked to the original request; 11:44:01 `answered`.

What it reported in that answer, verified:

1. **It could not read the request.** The request had gone into a room of two (the fallback
   from task 5.1 for asking one's own project's desk), and a room of two is readable by its two
   seats only — `sac join` does not change that. Sending there works. Probed alternative: a
   normal project room does not wake a desk that has not joined it (`wakes: []`, with the bus's
   own notice). So the room of two stays (it delivers and wakes), and the takeover context now
   says: if the room refuses you, ask the asker once (`sac dm <asker>`) to re-send; answer in
   the original room, linked — sending works where reading does not.
2. **"Unaddressed, wakes nobody" was false in a room of two** — the bus lists both other seats
   in `wakes`. The context now states the rule as the bus applies it.
3. Also seen here: the handover carried no predecessor session, because a gone desk has no
   inventory row. It is now taken from the predecessor's mandate (`session_ids`).
