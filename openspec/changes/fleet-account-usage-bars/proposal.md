## Why

The fleet screen shows what every agent is doing and — since `fleet-tab-cache-heat` —
what a keystroke costs in cache. It says nothing about the limit that actually stops
the work: the account's rolling 5-hour and 7-day quota. That number exists, is
already measured on this machine, and is visible only in a **separate desktop
window** (the Control Center), which is not open while anyone is watching the fleet.

The gap is not theoretical. Measured 2026-08-27, live against `claude.ai`, one
account stood at **96 % of its 7-day window with `severity: critical`** while its
5-hour window read 18 %. Nothing on the fleet screen could have said so, and the
7-day window resets in a day — which is exactly the horizon on which somebody
decides whether to start another agent.

## What Changes

- **The measurement becomes a framework capability, not a GUI internal.** The
  account resolution and the `claude.ai` usage call currently live inside a
  `QThread` in `gui/workers/usage.py`, importable only with PySide6 loaded. They
  move to a headless module so the web server, the CLI and the Control Center all
  read one source. The Control Center's own behaviour does not change.
- **A new read-only endpoint** answers the fleet screen with one entry per
  configured account: the two windows' utilisation, when each resets, the
  server-reported severity, and — where the upstream answer carries them — the
  per-model scoped windows.
- **The fleet header gains a compact strip of bars**, one row per account, in the
  same two-stripe shape the Control Center already uses: consumption above,
  elapsed time below, so "ahead of budget" is legible without arithmetic. It sits
  in the header because the quota is an account-wide fact, not a per-agent one.
- **Absent is never drawn as zero.** Measured the same day, one of three reachable
  accounts answered `200` with `five_hour: null` and `seven_day: null` — reachable,
  and unmeasured. An empty bar would read as "nothing consumed" and invite exactly
  the wrong decision, so that state gets its own mark.
- **The upstream call is polled and cached server-side, never issued per browser
  request.** Three accounts × 2 calls answered in 0.64–0.71 s each; a screen that
  refreshes on every render would turn a read into a rate-limited dependency.
- **No credential ever reaches the browser.** The session keys and OAuth tokens
  stay on the server; the response carries percentages, timestamps and names.

## Capabilities

### New Capabilities
- `account-usage-source`: headless, GUI-free measurement of an account's rolling
  usage windows — which accounts are configured, how each is authenticated, what
  the upstream answer means, and how an unmeasured window is distinguished from an
  empty one.
- `fleet-usage-bars`: what the fleet screen draws from that measurement — the
  two-stripe bar per window, the severity colouring, the unmeasured mark, and the
  staleness of the last poll.

### Modified Capabilities
<!-- None. `usage-display` and `multi-account-usage` describe the Control Center's
     rendering and account handling; both keep every requirement they have. The
     worker is re-pointed at the shared module, which is an implementation move,
     and the change proves it by re-measuring the Control Center's own output. -->

## Impact

- **New:** a headless usage module under `lib/set_orch/`, an API module registered
  in `lib/set_orch/api/__init__.py`, a `web/src/lib/` renderer beside
  `fleetCacheHeat.ts`, and the header strip in `web/src/pages/Fleet.tsx`.
- **Changed:** `gui/workers/usage.py` delegates instead of implementing.
- **Depends on** `curl_cffi` for the Cloudflare-fronted endpoint — already a
  dependency of the GUI path, with the same curl/urllib fallback chain, and every
  fallback must keep the "unmeasured, not zero" distinction.
- **Reads** `~/.config/set-core/claude-session.json` and `cc-accounts.json`. Both
  hold live credentials; nothing derived from them is persisted, logged, or sent
  to the browser beyond the account's display name.
