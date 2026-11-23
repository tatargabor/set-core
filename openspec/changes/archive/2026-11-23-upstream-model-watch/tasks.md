## 1. Core check (Layer 1, `lib/set_orch/providers/upstream.py`)

- [x] 1.1 Parse the overview markdown: anchored "Claude API ID" / "Claude API alias" rows → per-column (id, alias) pairs; zero rows → no ids [REQ: the-upstream-list-is-read-from-the-public-overview-s-id-rows-only]
- [x] 1.2 Fetch with no credential, 10 s timeout; any failure / non-2xx / zero ids → `unknown` with reason [REQ: a-check-that-could-not-measure-reports-unknown-never-current]
- [x] 1.3 Coverage: exact id or alias in `DEFAULT_MODEL_IDS` values (`[1m]` stripped), or pass-through family; report missing id + what the family shorthand resolves to [REQ: an-upstream-id-set-core-does-not-ship-is-reported-as-behind]
- [x] 1.4 Machine catalogue diff: `ANTHROPIC_MODEL_NAMES` minus the declared `anthropic` models, with the config path; skipped (and said) when no anthropic provider [REQ: a-shipped-name-missing-from-the-machine-catalogue-is-reported]
- [x] 1.5 Cache `~/.cache/set-core/upstream-models.json` (ids + fetched_at), 24 h, `refresh` bypass, failed fetch never overwrites [REQ: the-fetched-list-is-cached-for-a-day-and-can-be-refreshed]
- [x] 1.6 Logging per code-quality rule; no write outside the cache file [REQ: the-check-only-advises]

## 2. Surfaces

- [x] 2.1 `set-providers upstream [--refresh] [--json]`, exit 0/1/2, advice text [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog]
- [x] 2.2 `GET /api/fleet/models/upstream` (sync route, same function) [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog]
- [x] 2.3 Start dialog notice for `behind` / `unknown`; nothing for `current`; route failure → `unknown`, never blocks start [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog]

## 3. Tests and verification

- [x] 3.1 Python unit tests: fixture of the real table, link-slug and Bedrock rows ignored, shape change → unknown, network error → unknown, sonnet behind, fable covered, haiku via alias, machine diff, cache reuse / refresh / failed-refresh-keeps-cache, config bytes unchanged, CLI exit codes [REQ: an-upstream-id-set-core-does-not-ship-is-reported-as-behind]
- [x] 3.2 Web unit test for the notice (behind shown, current silent, route 500 → unknown + start still offered) [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog]
- [x] 3.3 Stash-and-rerun: the new tests fail without the implementation [REQ: a-check-that-could-not-measure-reports-unknown-never-current]
- [x] 3.4 Run `set-providers upstream` against the live page and record the output [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog]
- [x] 3.5 Visual check in the browser: open the start dialog on the running dashboard and look at the notice [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog]

## Evidence (2026-09-29)

- Python: `uv run --no-project --with pytest --with fastapi --with pyyaml python -m pytest tests/unit/test_providers_upstream.py` → 17 passed. Mutations, each restore byte-checked with `cmp`: zero ids counted as measured → 1 failed; unanchored row parsing → 6 failed; pass-through dropped → 2 failed.
- Web: `tests/unit/fleetProviders.test.tsx` → 31 passed. Mutation "failed read is silent" → 2 failed. Full suite: 4 failed / 1542. Those are the 4 known `designDrift` FleetWirePanel hits (B-150) plus the `fleetSurface` 7.4 / `fleetTileClick` tests, which gave 4 then 3 failures on identical source (B-136/B-149). None touch the start dialog.
- Live: `set-providers upstream` → exit 1, `Anthropic lists claude-sonnet-5-5, which set-core does not ship; sonnet currently resolves to claude-sonnet-4-6`.
- Browser: the start dialog, served through a throwaway proxy on :7401 (new route from this tree, everything else from the running :7400), shows `Anthropic lists claude-sonnet-5-5 — update set-core` with data-verdict=behind, and the start button still present. The shared set-web was NOT restarted, so :7400 serves the new bundle without the route, and shows "could not be checked" until its next restart (AC-14 behaviour).

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the page has a Claude API ID row with claude-sonnet-5-5 and a link slug claude-prompting-best-practices THEN only the former is parsed [REQ: the-upstream-list-is-read-from-the-public-overview-s-id-rows-only, scenario: ids-come-from-the-two-id-rows]
- [x] AC-2: WHEN the page has an Amazon Bedrock ID row THEN no id is taken from it [REQ: the-upstream-list-is-read-from-the-public-overview-s-id-rows-only, scenario: other-platforms-ids-are-ignored]
- [x] AC-3: WHEN the fetch raises a connection error THEN unknown with the reason [REQ: a-check-that-could-not-measure-reports-unknown-never-current, scenario: network-failure]
- [x] AC-4: WHEN the page has no Claude API ID row THEN unknown, not current [REQ: a-check-that-could-not-measure-reports-unknown-never-current, scenario: the-page-changed-shape]
- [x] AC-5: WHEN upstream lists claude-sonnet-5-5 and sonnet → claude-sonnet-4-6 THEN behind, naming both [REQ: an-upstream-id-set-core-does-not-ship-is-reported-as-behind, scenario: a-new-sonnet-is-published]
- [x] AC-6: WHEN upstream lists claude-fable-5-1 and fable is pass-through THEN not reported [REQ: an-upstream-id-set-core-does-not-ship-is-reported-as-behind, scenario: a-pass-through-family-is-covered]
- [x] AC-7: WHEN haiku's API ID is dated and shipped THEN not reported [REQ: an-upstream-id-set-core-does-not-ship-is-reported-as-behind, scenario: a-dated-id-matched-through-its-alias]
- [x] AC-8: WHEN the machine catalogue lacks opus-5-5 THEN behind, listed with the file path [REQ: a-shipped-name-missing-from-the-machine-catalogue-is-reported, scenario: a-machine-file-older-than-the-shipped-names]
- [x] AC-9: WHEN the cache is 2 h old and no refresh THEN no fetch, cached time shown [REQ: the-fetched-list-is-cached-for-a-day-and-can-be-refreshed, scenario: a-fresh-cache-is-reused]
- [x] AC-10: WHEN a refresh fails over yesterday's cache THEN unknown and the cache is kept [REQ: the-fetched-list-is-cached-for-a-day-and-can-be-refreshed, scenario: a-failed-refresh-keeps-the-last-good-list]
- [x] AC-11: WHEN behind THEN the provider config bytes are unchanged [REQ: the-check-only-advises, scenario: a-behind-verdict-changes-nothing]
- [x] AC-12: WHEN the CLI runs behind THEN exit 1 with the id and advice [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog, scenario: exit-codes]
- [x] AC-13: WHEN the dialog opens behind THEN the notice names claude-sonnet-5-5 [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog, scenario: the-dialog-names-the-gap]
- [x] AC-14: WHEN the route answers 500 THEN models and start remain, notice says could not check [REQ: the-verdict-is-visible-on-the-cli-the-api-and-the-start-dialog, scenario: the-report-route-is-down]
