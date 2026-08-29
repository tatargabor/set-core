## Why

This machine runs Claude Code through the GLM Coding Plan (z.ai), and its provider
credential already lives in `providers.json` — but the usage strip can only show
claude.ai accounts, so the plan the machine actually spends most of its quota on is
the one it cannot see. GLM exposes a monitor endpoint for exactly this
(`/api/monitor/usage/quota/limit`, measured live 2026-08-29), so the omission is
now cheaper to close than to keep.

## What Changes

- A second usage source is added beside the Claude account source: it discovers the
  GLM account from the machine's provider credential and reads its rolling quota
  windows from the provider's monitor endpoint.
- The poller learns to hold independent sources: each source is discovered and
  fetched in its own failure boundary, so one source raising cannot remove another
  source's accounts from the answer. The snapshot shape is unchanged; the GLM
  account simply appears in `accounts[]` with kind `glm`.
- GLM carries no severity upstream, so severity for that source is banded at
  measurement (≥70 warning, ≥90 critical), in one named place — the only banding
  the framework performs, and never an override of a severity an upstream stated.
- The strip renders the GLM account through the same account row path it already
  has (nothing on the strip is hardcoded), and its critical-mark wording stops
  attributing the band to "the service" — true no longer for every source.

## Capabilities

### New Capabilities

- `glm-usage-source`: discovering the GLM account from the machine's provider
  credential and reading its rolling quota windows from the z.ai monitor endpoint —
  discovery that is absent (not unreachable) when no credential is configured, the
  raw-credential auth the endpoint requires, window group and length derived from
  the upstream's own unit and number, epoch-millisecond reset times, the one local
  severity band, and the credential-never-travels rule.

### Modified Capabilities

- `account-usage-source`: the measured set becomes the union of independent
  sources — the discovery requirement gains the source-union and per-source failure
  scenarios, and the severity requirement changes from "upstream, never a local
  threshold" to "from upstream when the upstream states one; a source that states
  none may be banded in the one named place, and a stated severity is never
  overridden".
- `fleet-usage-bars`: the colour requirement's wording changes from "the severity
  the measurement carries" being upstream-defined to "the severity the measurement
  reports" — the screen still never computes a band of its own; what changes is
  that one source's band is set at measurement, not by z.ai.

## Impact

- `lib/set_orch/usage/` — new `glm.py`; `poller.py` gains a source list with
  per-source isolation; `__init__.py` exports and `default_sources()`.
- `lib/set_orch/server.py` — one line: the poller is constructed with
  `default_sources()` (the GLM source is injected at the server, never defaulted
  in the poller, so existing poller tests stay hermetic).
- `lib/set_orch/api/usage.py` — docstring only; no route or shape change.
- `web/src/lib/fleetUsageBars.ts` — window-label fallback from `window_seconds`;
  `toneFor` and the counting rules untouched.
- `web/src/components/FleetUsageStrip.tsx` — critical-mark wording only.
- No new HTTP route, so route ordering is untouched; no dependency changes.
