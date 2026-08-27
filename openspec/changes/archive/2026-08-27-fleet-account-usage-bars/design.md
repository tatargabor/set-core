## Context

The account's rolling quota is measured on this machine every 30 seconds already — by a
`QThread` inside the Control Center (`gui/workers/usage.py`), importable only where PySide6
loads. The fleet screen, which is where somebody decides whether to start another agent, has
no access to it: measured 2026-08-27, `lib/set_orch/api/` contains no usage endpoint at all.

What the upstream actually answers, measured the same day against three configured accounts
(2 network calls each, 0.64–0.71 s per account, all `200`):

- `five_hour` and `seven_day`, each `{utilization, resets_at, limit_dollars: null, …}`
- a `limits` array carrying the same figures already banded:
  `{kind, group, percent, severity, resets_at, scope, is_active}` — including a
  `weekly_scoped` entry naming one model
- one of the three accounts answered `200` with **both windows null**
- `seven_day_opus`, `seven_day_sonnet`, `seven_day_cowork` present as keys, all null on this plan

## Goals / Non-Goals

**Goals:**
- One measurement, three readers (fleet screen, Control Center, any CLI) — not a second copy
- The fleet header carries the two windows per account without the reader opening another app
- Unmeasured, unreachable and unconfigured stay distinguishable all the way to the pixel
- No credential crosses into the browser, a log, or a persisted artifact

**Non-Goals:**
- Estimating usage from local transcripts for the fleet screen (the Control Center keeps its own
  local fallback — that is an existing requirement of `usage-display` and is not being changed)
- Per-agent attribution, throttling, or any action taken on the number
- Touching the cache-heat marks, which measure a different thing on the same screen

## Decisions

### The module is Layer 1, headless, and PySide-free

`lib/set_orch/usage/` — account discovery, the upstream client with its transport fallbacks, and
a poller. Nothing project-type-specific enters it, so the layering rule is satisfied: an account
quota is not a web-project fact or a consumer-domain fact.

**Alternative rejected:** importing from `gui/` into the server. It would make the web service
depend on a desktop toolkit, and the GUI package is not on the server's import path.

### The Control Center delegates the API half, and keeps its local fallback

`UsageWorker` keeps being a `QThread` and keeps `fetch_local_usage`; only
`fetch_claude_api_usage` / `_fetch_org_usage` / `_api_get*` move behind the shared module. This
is deliberate asymmetry: the desktop window's local estimate is a shipped requirement with its
own scenarios, and removing it here would be a silent spec change in a capability this proposal
says it is not modifying.

**How it is proven a move and not a rewrite:** the Control Center's rendered strip is measured
before and after against the same accounts, and the two must agree.

### The organization lookup is cached separately from the usage read

Today each poll costs two calls per account: `/organizations`, then
`/organizations/{uuid}/usage`. The org uuid does not change between polls. Caching it for the
process lifetime halves the upstream traffic — at three accounts and a 60 s poll that is 3
calls/minute instead of 6 — and the usage read is the only one that needs to be fresh.

**Failure handling:** a rejected usage call invalidates the cached org uuid once, so a moved or
re-scoped account re-resolves instead of failing forever.

### The poller runs in the server lifespan, not on the request path

`server.py` already starts and stops the watcher and the unified service in its `lifespan`; the
usage poller joins them. A caller reading the endpoint gets the last completed measurement.

**Alternative rejected:** a lazy TTL cache refreshed by the first request after expiry. It reads
as "cached", but the first reader after every interval pays the latency and, more importantly,
the number of upstream calls then follows the number of browsers, which is exactly the coupling
the spec forbids.

### The endpoint is its own router, registered before the project routers

`/api/usage/accounts`, in `lib/set_orch/api/usage.py`, included in `api/__init__.py` alongside
`fleet_router`. `fleet.py` documents why order matters there — a project-name router can swallow
a literal path segment — so the new router takes the same precaution rather than discovering the
same problem again.

The payload is a list of account records: display name, auth kind, an outcome
(`measured` / `unmeasured` / `unreachable`), the windows with `utilization`, `resets_at`,
`severity`, any `scope`, and a `measured_at` for the whole answer. Every window figure is
nullable, and null means *not measured* — the same shape `fleet-tab-cache-heat` chose for its
absent cache, and for the same reason.

### The strip renders like the cache heat does: server decides state, client draws it

`web/src/lib/fleetUsageBars.ts` beside `fleetCacheHeat.ts`, exporting one `mark()`-style function
that turns a record into what to draw. The **elapsed** stripe is the one computed in the browser
(from `resets_at` and the window length) — and that is a deliberate exception, because it changes
every second and would otherwise be as stale as the poll. Consumption, severity and outcome all
come from the server, so the two clocks can never disagree about whether a window is critical.

**Alternative rejected:** deriving severity client-side from the percentage. Two thresholds for
one fact, and the upstream already states it — measured: a 96 % window arrived labelled
`critical` without anyone here choosing 96.

### Two stripes, matching the desktop widget, and one row per account

Consumption above, elapsed below, in one bar per window, per account row — the shape
`DualStripeBar` has used since `usage-display` shipped. Copying it is the point: the two screens
show the same fact and should not teach two readings of it.

## Risks / Trade-offs

- **[The upstream is undocumented and can change shape]** → Every field is read defensively and a
  missing field becomes *unmeasured*, never a zero. The one field whose absence is already
  observed (a null window on a reachable account) has its own requirement and its own test.
- **[Cloudflare blocks the plain transports]** → Same fallback chain as today (curl_cffi → curl →
  urllib); a total failure is reported as unreachable, which is a state the screen can draw.
- **[Credentials in a new process]** → The server already runs as the user and reads their config;
  what is new is a second reader of the same files. The boundary enforced here is that nothing
  derived from them is serialised: the response carries names, percentages and timestamps.
- **[A third clock]** → Poll time, upstream `resets_at`, and the browser now all appear in one
  strip. Mitigated by the split above: only the elapsed stripe is browser-derived, and the answer
  always carries `measured_at` so a stale strip is readable rather than merely wrong.
- **[Header crowding]** → The fleet header already carries a title, a toggle and up to four chips.
  The strip is one compact row per account and must collapse — with the critical-state carve-out
  the spec requires, so collapsing cannot hide a red account.

## Migration Plan

1. Land the module and its tests with no caller — the Control Center still runs its own copy.
2. Re-point `UsageWorker`, measure the desktop strip before/after, and only then delete the moved
   code paths.
3. Add the endpoint and poller; verify from the running server that a read makes no upstream call.
4. Add the strip. Look at it in the browser, with a critical account and with an unmeasured one.

Rollback is per-step: the strip and the endpoint are additive, and step 2 is a revert of one file.

## Open Questions

- **The scoped windows** (`weekly_scoped`, `seven_day_opus`, `seven_day_sonnet`) are carried by the
  source but the strip does not draw them in this change. All were null on the measured plan except
  one model-scoped window at 2 %, so there is nothing here to design a layout against yet.
- **Which account the agents on this machine actually consume** stays unanswered by design: it is
  measurable for 4 of 40 recent sessions, and the strip therefore reports accounts, not agents.
  If the transcript's owning-account field becomes universal, per-project attribution becomes a
  separate change with its own measurement.
