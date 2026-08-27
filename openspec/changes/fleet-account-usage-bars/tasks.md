## 1. The headless measurement module

- [x] 1.1 Create `lib/set_orch/usage/accounts.py`: discover usage-capable accounts from both credential stores, each carrying its auth kind, dropping entries with no usable credential [REQ: accounts-are-discovered-from-the-machine-s-configuration-with-their-auth-kind]
- [x] 1.2 Unit-test discovery against fixtures for: both stores populated, an entry with an empty credential, and neither store present — with fixture names and addresses that belong to no real person [REQ: accounts-are-discovered-from-the-machine-s-configuration-with-their-auth-kind]
- [x] 1.3 Create `lib/set_orch/usage/client.py`: the upstream read with the curl_cffi → curl → urllib fallback chain, cookie auth for one kind and bearer auth for the other, returning a typed record [REQ: usage-is-read-from-the-upstream-account-api-never-estimated]
- [x] 1.4 Cache the organization uuid per account for the process lifetime, and invalidate it once on a rejected usage call [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [x] 1.5 Parse the answer so a null window becomes `unmeasured`, never `0` — every window figure nullable, with the outcome stated per account and per window [REQ: a-reachable-account-with-no-measured-window-is-not-a-zero]
- [x] 1.6 Carry the upstream `severity` verbatim and any scoped window with its scope name; compute no band locally and synthesise no scope [REQ: severity-and-scoped-windows-come-from-upstream-not-from-a-local-threshold]
- [x] 1.7 Unit-test the parser against a recorded upstream answer with: a labelled-critical weekly window, a model-scoped window, and an account whose windows are both null [REQ: a-reachable-account-with-no-measured-window-is-not-a-zero]
- [x] 1.8 Assert in a test that the serialised record contains no credential substring, and that the module's log calls name counts and outcomes only [REQ: no-credential-leaves-the-measuring-process]
- [x] 1.9 Add a test that a failed read of one account does not remove the other accounts from the answer [REQ: usage-is-read-from-the-upstream-account-api-never-estimated]

## 2. The poller

- [x] 2.1 Create `lib/set_orch/usage/poller.py`: refresh on a fixed interval, hold the last completed measurement with its `measured_at`, and keep serving it when a refresh fails [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [x] 2.2 Start and stop the poller in `server.py`'s `lifespan`, beside the watcher and the unified service [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [x] 2.3 Test that N reads between two polls issue zero upstream requests — by counting calls on a fake transport, not by timing [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [x] 2.4 Test that a failing refresh after a good one leaves the earlier figures and their original `measured_at` intact [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]

## 3. The endpoint

- [x] 3.1 Create `lib/set_orch/api/usage.py` with `GET /api/usage/accounts` answering from the poller; register it in `api/__init__.py` before the project routers [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [x] 3.2 Verify no route already claims `/api/usage/...` — check the registered path list on the built app, not by reading files [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [x] 3.3 API test: the response body carries no session key and no bearer token for any account state [REQ: no-credential-leaves-the-measuring-process]
- [x] 3.4 API test: an unconfigured machine answers an empty account list, distinct from an unreachable account [REQ: an-unmeasured-window-is-marked-never-drawn-as-an-empty-bar]

## 4. The Control Center delegates

- [ ] 4.1 Record the Control Center's current strip output for the configured accounts — the values it renders, before any change [REQ: usage-is-read-from-the-upstream-account-api-never-estimated]
- [ ] 4.2 Re-point `UsageWorker`'s API path at `lib/set_orch/usage/`, keeping the `QThread`, the signal shape and `fetch_local_usage` exactly as they are [REQ: usage-is-read-from-the-upstream-account-api-never-estimated]
- [ ] 4.3 Re-measure the strip and show it matches 4.1 field by field; only then delete the moved code paths from `gui/workers/usage.py` [REQ: usage-is-read-from-the-upstream-account-api-never-estimated]
- [ ] 4.4 Run the existing GUI tests that cover usage and the Chrome cookie path, and report the before/after counts [REQ: usage-is-read-from-the-upstream-account-api-never-estimated]

## 5. The strip

- [ ] 5.1 Create `web/src/lib/fleetUsageBars.ts` beside `fleetCacheHeat.ts`: one function turning an account record into what to draw — outcome, the two stripe fractions, severity tone, and the unmeasured mark [REQ: each-window-draws-consumption-against-elapsed-time]
- [ ] 5.2 The elapsed stripe is computed in the browser from `resets_at` and the window length; consumption, severity and outcome are taken from the server unchanged [REQ: each-window-draws-consumption-against-elapsed-time]
- [ ] 5.3 Unit-test the renderer: consumption ahead of elapsed, consumption behind elapsed, a null window, an unreachable account, an empty account list [REQ: an-unmeasured-window-is-marked-never-drawn-as-an-empty-bar]
- [ ] 5.4 Unit-test that a critical severity produces the critical tone and a normal one never does, whatever the percentage [REQ: colour-states-the-upstream-severity-and-one-weight-means-one-thing]
- [ ] 5.5 Render the strip in the fleet header of `web/src/pages/Fleet.tsx`, one row per account, both windows per row, with data attributes a test can aim at [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [ ] 5.6 Assert in a test that no consumption mark is rendered on any agent tab or tile [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [ ] 5.7 Show `measured_at` on the strip once the measurement is older than one polling interval, and keep the last good figures when a refresh fails [REQ: the-strip-says-how-old-its-measurement-is]
- [ ] 5.8 Make the strip collapsible, and keep a critical window marked in the collapsed state [REQ: collapsing-the-strip-never-hides-a-critical-account]
- [ ] 5.9 Test that the header and the screen below render fully when the usage request fails or never returns [REQ: the-header-renders-whether-or-not-the-measurement-arrived]
- [ ] 5.10 Verify the critical colour is used for nothing decorative in the strip [REQ: colour-states-the-upstream-severity-and-one-weight-means-one-thing]

## 6. Verification on the running system

- [ ] 6.1 Against the running server, read `/api/usage/accounts` twice inside one interval and show from the logs that no upstream call was made [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken]
- [ ] 6.2 `pnpm build` in `web/`, so port 7400 serves the built strip [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [ ] 6.3 **LOOK AT IT (required, not optional):** open the fleet screen in Chrome and report what is actually on screen — every account row, both windows, the two stripes, and whether the header is crowded. If the browser cannot be reached, this task stays OPEN and the commit says so [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [ ] 6.4 **LOOK AT the unmeasured state**: with an account whose windows are null, confirm on screen that it shows the unmeasured mark and not an empty bar [REQ: an-unmeasured-window-is-marked-never-drawn-as-an-empty-bar]
- [ ] 6.5 **LOOK AT the collapsed state** with a critical account present, and report whether the critical mark survives the collapse [REQ: collapsing-the-strip-never-hides-a-critical-account]
- [ ] 6.6 Stash-and-rerun each new test that claims to prove a fix, and record which ones failed without the change [REQ: a-reachable-account-with-no-measured-window-is-not-a-zero]
- [ ] 6.7 Run `set-leakscan --staged` before committing; no account address or credential fragment reaches the repository [REQ: no-credential-leaves-the-measuring-process]

## Acceptance Criteria (from spec scenarios)

### account-usage-source

- [ ] AC-1: WHEN the machine holds both browser-derived session keys and OAuth-token accounts THEN every one is reported with its own auth kind [REQ: accounts-are-discovered-from-the-machine-s-configuration-with-their-auth-kind, scenario: both-credential-stores-hold-accounts]
- [ ] AC-2: WHEN an entry carries no session key or access token THEN it is not reported as an account [REQ: accounts-are-discovered-from-the-machine-s-configuration-with-their-auth-kind, scenario: a-store-holds-an-entry-with-no-usable-credential]
- [ ] AC-3: WHEN neither store exists or both are empty THEN the answer is an empty account list, distinct from an unmeasurable account [REQ: accounts-are-discovered-from-the-machine-s-configuration-with-their-auth-kind, scenario: no-credentials-at-all]
- [ ] AC-4: WHEN the account API returns the usage document THEN the windows reported are the ones it carries [REQ: usage-is-read-from-the-upstream-account-api-never-estimated, scenario: the-upstream-answers]
- [ ] AC-5: WHEN no transport reaches the upstream for an account THEN it is reported unreachable with no window figures [REQ: usage-is-read-from-the-upstream-account-api-never-estimated, scenario: every-transport-fails]
- [ ] AC-6: WHEN a window object is null on a reachable account THEN it is marked unmeasured, distinguishably from measured-at-zero [REQ: a-reachable-account-with-no-measured-window-is-not-a-zero, scenario: a-window-the-upstream-did-not-fill]
- [ ] AC-7: WHEN one window carries a figure and the other does not THEN the first is reported and the second marked unmeasured [REQ: a-reachable-account-with-no-measured-window-is-not-a-zero, scenario: one-window-measured-and-one-not]
- [ ] AC-8: WHEN a window arrives carrying a severity THEN that severity is what the record reports [REQ: severity-and-scoped-windows-come-from-upstream-not-from-a-local-threshold, scenario: the-upstream-labels-a-window]
- [ ] AC-9: WHEN the upstream reports a model-scoped window THEN it is carried with its scope, apart from the account-wide window [REQ: severity-and-scoped-windows-come-from-upstream-not-from-a-local-threshold, scenario: a-model-scoped-window-is-present]
- [ ] AC-10: WHEN the upstream reports no scoped window THEN none is reported and none is derived [REQ: severity-and-scoped-windows-come-from-upstream-not-from-a-local-threshold, scenario: no-scoped-window-is-reported]
- [ ] AC-11: WHEN a caller reads twice within one polling interval THEN both reads come from the same measurement and no upstream request is made [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken, scenario: two-reads-between-two-polls]
- [ ] AC-12: WHEN a refresh fails and an earlier measurement exists THEN the earlier one is still served with its own timestamp [REQ: the-measurement-is-polled-and-every-answer-says-when-it-was-taken, scenario: a-poll-fails-after-a-successful-one]
- [ ] AC-13: WHEN a usage record is serialised THEN no field contains the credential used to obtain it [REQ: no-credential-leaves-the-measuring-process, scenario: the-answer-is-inspected]
- [ ] AC-14: WHEN a request is rejected for an account THEN the failure is reported and logged without the credential [REQ: no-credential-leaves-the-measuring-process, scenario: an-account-fails-to-authenticate]

### fleet-usage-bars

- [ ] AC-15: WHEN several usage-capable accounts are configured THEN the header carries one row per account, each naming it [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact, scenario: more-than-one-account-is-configured]
- [ ] AC-16: WHEN agent tabs and tiles render THEN no account-consumption mark appears on any of them [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact, scenario: an-agent-tab-is-drawn]
- [ ] AC-17: WHEN consumption exceeds the elapsed share of a window THEN the consumption stripe reads longer than the elapsed stripe [REQ: each-window-draws-consumption-against-elapsed-time, scenario: consumption-ahead-of-elapsed-time]
- [ ] AC-18: WHEN an account carries both windows THEN both are drawn on the row, each labelled [REQ: each-window-draws-consumption-against-elapsed-time, scenario: both-windows-are-shown]
- [ ] AC-19: WHEN a window's severity is critical THEN its mark is drawn in the critical colour [REQ: colour-states-the-upstream-severity-and-one-weight-means-one-thing, scenario: a-window-arrives-labelled-critical]
- [ ] AC-20: WHEN a window's severity is normal THEN the critical colour is not used, whatever the percentage [REQ: colour-states-the-upstream-severity-and-one-weight-means-one-thing, scenario: a-window-arrives-labelled-normal]
- [ ] AC-21: WHEN a reachable account carries a null window THEN the unmeasured mark is shown and no bar is drawn [REQ: an-unmeasured-window-is-marked-never-drawn-as-an-empty-bar, scenario: a-reachable-account-with-a-null-window]
- [ ] AC-22: WHEN an account could not be reached THEN its row says so, distinguishably from merely unmeasured windows [REQ: an-unmeasured-window-is-marked-never-drawn-as-an-empty-bar, scenario: an-unreachable-account]
- [ ] AC-23: WHEN no usage-capable account is configured THEN the strip says so rather than drawing empty bars [REQ: an-unmeasured-window-is-marked-never-drawn-as-an-empty-bar, scenario: no-accounts-are-configured]
- [ ] AC-24: WHEN the measurement is older than one polling interval THEN the strip states when it was taken [REQ: the-strip-says-how-old-its-measurement-is, scenario: the-measurement-goes-stale]
- [ ] AC-25: WHEN a refresh fails after a good measurement THEN the earlier figures stay on screen marked with their age [REQ: the-strip-says-how-old-its-measurement-is, scenario: a-refresh-fails]
- [ ] AC-26: WHEN the strip is collapsed and an account holds a critical window THEN a mark stating that stays visible [REQ: collapsing-the-strip-never-hides-a-critical-account, scenario: the-strip-is-collapsed-with-a-critical-account-present]
- [ ] AC-27: WHEN the strip is collapsed and nothing is critical THEN no critical mark is shown [REQ: collapsing-the-strip-never-hides-a-critical-account, scenario: the-strip-is-collapsed-with-nothing-critical]
- [ ] AC-28: WHEN the usage request fails or has not returned THEN the header and the screen below render as today, and the strip states the measurement is unavailable [REQ: the-header-renders-whether-or-not-the-measurement-arrived, scenario: the-usage-endpoint-does-not-answer]
