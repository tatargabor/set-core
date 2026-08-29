# Design: add-glm-usage-monitoring

## Context

The usage subsystem (`lib/set_orch/usage/`) measures claude.ai accounts — discovered from
`claude-session.json` / `cc-accounts.json`, read by `UsageClient`, polled by `UsagePoller`,
served by `GET /api/usage/accounts`, rendered by `FleetUsageStrip` (which draws whatever the
snapshot carries; nothing hardcoded). The machine's GLM credential lives separately, in
`providers.json` → `providers.glm.credential` (mode-0600 enforced by `providers/config.py`,
which **raises** rather than returning empty). The z.ai monitor endpoint was probed live on
2026-08-29: `GET {host}/api/monitor/usage/quota/limit`, header `Authorization: <token>` raw
(no Bearer — confirmed against z.ai's official `query-usage.mjs`), answering
`data.limits[]` of `{type, unit, number, percentage, nextResetTime(epoch-ms)}`; two limits
today (unit 3×5 = five-hour credits, unit 6×1 = weekly credits); no severity field.

## Goals / Non-Goals

**Goals:** GLM appears in the strip as an account like any other; a failing source cannot
damage another; existing tests and call sites unchanged.

**Non-Goals:** per-model/tool usage endpoints (shaped for, not read); cost in currency;
any write to `providers.json`; new HTTP routes; per-source staleness machinery.

## Decisions

**D1 — GLM is a second *source*, not a Claude account.** A new `GlmUsageClient` with its own
transport (curl → urllib; no browser TLS impersonation needed for a plain JSON API) and its
own discovery (`discover_glm_account`, loading through `providers.config.load_or_legacy`).
`AccountUsage`/`UsageWindow` are reused as-is: the snapshot shape and the frontend stay
untouched, and `kind: "glm"` travels with the account the way `web`/`cc` already do.
Alternative rejected: teaching `UsageClient` a second upstream — its org-uuid cache and
Cloudflare transport are claude.ai-specific, and the seams would multiply.

**D2 — Sources are injected at the server, never defaulted in the poller.** `UsagePoller`
gains `sources: Optional[List[UsageSource]] = None`, None meaning today's single Claude
source — every existing constructor call and test keeps its behaviour. `server.py` passes
`default_sources()`. Alternative rejected: a GLM default inside the poller would make every
existing poller test read the machine's real `providers.json` (which holds a live token) —
non-hermetic and machine-dependent. Two different config-dir overrides make this worse:
`usage/accounts.py` honours `WT_CONFIG_DIR`, `providers/config.py` honours
`SET_CONFIG_DIR`/`XDG_CONFIG_HOME` — so tests must inject the loader, and only an injected
source list keeps them honest.

**D3 — Per-source failure boundaries in `refresh()`.** Today the whole refresh sits in one
try/except. Each source is now discovered and fetched inside its own: a source whose
discovery raises keeps its previous figures and records the failure, the others proceed and
stamp a fresh `measured_at`. `providers.config.load()` raising on an *unrelated* provider's
malformed `model_aliases` is the concrete case this decision exists for.

**D4 — Severity banded in `GlmUsageClient`, never in the frontend.** `toneFor(severity)` is
test-asserted to give the percentage no vote; the critical count, the tones and the compact
marks all key off the reported severity already. Banding at measurement (≥70 warning,
≥90 critical, module-level constants documented as set-core's own) means zero change to any
of it. This is the one deliberate deviation from `client.py`'s "no second opinion" comment —
which is about *overriding* a stated severity; z.ai states none, so the alternative is a 96 %
window rendering calm.

**D5 — Window length computed from `unit × number`, not a fixed table.** 3×5 → 18 000 s,
6×1 → 604 800 s. The frontend keeps `WINDOW_LABEL` for the known groups and falls back to
deriving the label from `window_seconds` for anything else; an unknown length means no
elapsed stripe, never a guessed one.

**D6 — No new route; `api/usage.py` docstring only.** The GLM account arrives inside the
existing `accounts[]`, so route ordering (finding CB-16) is untouched.

## Risks / Trade-offs

- [The raw no-Bearer `Authorization` header reads like a bug] → a test asserts the exact
  header, with a comment naming the measured upstream behaviour.
- [Epoch-ms `nextResetTime` misparsed as seconds] → convert in Python with a documented
  1e11 threshold; unparseable → absent, never guessed.
- [`headlineWindows()` excludes scoped windows] → GLM windows carry `scope: null`, so a
  future `TOKENS_LIMIT` entry cannot silently vanish from the compact mark.
- [Two upstreams polled every 60 s] → one extra JSON GET per minute against a plan-level
  quota endpoint; acceptable, and the route still never drives an upstream call.

## Migration Plan

Additive: a machine with no `glm` provider sees exactly what it sees today (no GLM row,
never an unreachable row). Rollback is reverting the server wiring — the source is inert
unless injected.

## Open Questions

None — the endpoint shape and the auth form are measured, and the frontend path is
already generic.
