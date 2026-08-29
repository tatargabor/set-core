# Tasks: add-glm-usage-monitoring

## 1. GLM source module

- [ ] 1.1 Create `lib/set_orch/usage/glm.py`: `KIND_GLM`, `discover_glm_account(loader=None)`
      (default `providers.config.load_or_legacy`; catch `ProviderError` + `OSError` → `[]`,
      debug-level log; no usable credential → no account), `monitor_base_url()`,
      `GlmUsageClient` (injectable transport; GET `{host}/api/monitor/usage/quota/limit`;
      raw `Authorization: <token>` header, no Bearer; `_parse` generic over limit `type`;
      `utilization` = `percentage` only — never synthesised; `resets_at` epoch-ms → ISO UTC
      with documented 1e11 seconds/milliseconds threshold, unparseable → None;
      `_severity` ≥90 critical / ≥70 warning as module constants documented as set-core's own;
      `window_seconds` = unit × number, unknown → None; `scope` always None;
      `fetch`/`fetch_all` never raise, one failing account never shortens the answer)
- [ ] 1.2 Write `tests/unit/test_usage_glm.py`: discovery (configured credential, no
      provider, unreadable config, unparsable base_url, legacy file), transport (exact raw
      header asserted, host derivation, rejection → unreachable, transport failure →
      unreachable, one failing account), windows (document's windows reported, unknown type
      kept as own kind, 5 h → session/18 000 s, weekly → weekly/604 800 s, unknown unit → no
      elapsed stripe, epoch-ms → ISO UTC, seconds not misdated, unparseable → None),
      severity (90/70 boundaries, no percentage → unmeasured not zero, measured zero
      distinct), credential never serialised or logged

## 2. Poller sources

- [ ] 2.1 `lib/set_orch/usage/poller.py`: `UsageSource(discover, client)` dataclass;
      `UsagePoller(..., sources=None)` with None → today's single Claude source (all existing
      call sites unchanged); `refresh()` loops sources, each inside its own try/except —
      a source whose discovery raises keeps its previous figures, records the failure,
      and the other sources proceed and stamp a fresh `measured_at`
- [ ] 2.2 `lib/set_orch/usage/__init__.py`: export the new names; `default_sources()`
      returning the Claude pair plus the GLM pair
- [ ] 2.3 `lib/set_orch/server.py`: construct the poller with `sources=default_sources()`
      — the only server change
- [ ] 2.4 Extend `tests/unit/test_usage_poller.py`: two sources reach the snapshot; one
      source raising does not remove the other's accounts; the raising source keeps its
      previous figures; the default source list contains no GLM source
- [ ] 2.5 Extend `tests/unit/test_usage_api.py`: a `kind: glm` account in the body still
      carries no credential

## 3. Frontend

- [ ] 3.1 `web/src/lib/fleetUsageBars.ts`: window-label fallback deriving the span from
      `window_seconds` when the group is not in `WINDOW_LABEL`; `toneFor`, `markWindow`,
      `criticalCount`, `headlineWindows`, `stripState` untouched
- [ ] 3.2 `web/src/components/FleetUsageStrip.tsx`: reword the two critical-mark strings so
      they no longer attribute the band to the service ("over the critical threshold", not
      "windows the service calls critical")
- [ ] 3.3 Extend `web/tests/unit/fleetUsageBars.test.ts`: GLM row beside Claude rows;
      seconds-derived label for an unknown group; known groups keep their table labels; no
      elapsed stripe when length unknown; server-reported severity colours through; GLM
      critical window counted
- [ ] 3.4 Extend `web/tests/unit/fleetUsageStrip.test.tsx`: GLM bars beside Claude bars
      while compact; GLM as a named row in the detail; critical wording no longer claims the
      service; existing `no banding by percentage` tripwires still green

## 4. Verify

- [ ] 4.1 pytest: new and touched suites set-diffed against a freshly run baseline
      (`regression-baseline` skill)
- [ ] 4.2 vitest: the three touched suites, including the two severity tripwires
- [ ] 4.3 Visual check in the browser against the running dashboard: GLM bar pair beside
      the Claude bars, detail row named GLM with 5 h / 7 d windows, percentages sane against
      the z.ai dashboard, Claude rows unchanged. If the browser cannot be reached, this task
      stays open and is reported as such
- [ ] 4.4 Record the change in the living record if any consumer-facing behaviour note is
      warranted; commit with the spec artifacts
