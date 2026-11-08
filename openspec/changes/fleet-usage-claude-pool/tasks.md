## 1. The scan in core

- [x] 1.1 `lib/set_orch/usage/chrome_scan.py` (core): the scanner moved from `gui/workers/chrome_cookies.py`; keyring password by attribute first, walk with per-item boundary as the fallback [REQ: the-keyring-password-is-found-despite-a-broken-item] — 2026-11-08: moved with `git mv`; keyring script shared by both interpreters
- [x] 1.2 `gui/workers/chrome_cookies.py` re-exports the core module and keeps `ChromeScanWorker`; `tests/gui/test_17_chrome_cookies.py` targets the core module [REQ: the-keyring-password-is-found-despite-a-broken-item] — test_17: 29 passed, 1 skipped before and after (run with the dashboard's interpreter; the venv lacks libGL)
- [x] 1.3 `rescan(directory)`: scan, merge (manual kept), atomic write 0600, no write on an empty or failed scan [REQ: a-rescan-replaces-scanned-sessions-and-keeps-manual-ones]

## 2. The route

- [x] 2.1 `POST /api/usage/accounts/rescan` (core API): non-blocking lock → 409, refresh the poller after a write, answer `{found, reason, snapshot}` with no key [REQ: the-rescan-measures-again-and-answers-without-secrets]

## 3. The strip

- [x] 3.1 `web/src/lib/fleetUsageBars.ts`: merge `web`+`cc` rows of one name; distinct labels over all Claude accounts in the measurement [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [x] 3.2 `claudePool()`: equal-share mean consumed / mean elapsed, pace = Σu/Σe, left-out rows named [REQ: the-claude-pool-reads-the-week-against-the-time-that-has-passed]
- [x] 3.3 `FleetUsageStrip.tsx`: the pool mark first, Claude rows by short label, then the other providers; "rescan Chrome" in the detail with its result [REQ: the-browser-sessions-can-be-rescanned-from-the-strip]

## 4. Verification

- [x] 4.1 Unit tests: rescan merge/0600/no-write/409/no-secret; keyring fallback; merge, labels, pool math in vitest [REQ: a-rescan-replaces-scanned-sessions-and-keeps-manual-ones] — 8 Python tests (`tests/unit/test_usage_rescan.py`), usage suite 38 passed; vitest 72 passed in the two strip files. Mutations caught: no attribute lookup (1 fail), no per-item boundary (1 fail), no merge (2 fail), no distinct labels (3 fail), no amber tone (1 fail). Full web suite: 8 failures in 4 untouched files; HEAD in a clean worktree fails 5 of them, and the other 3 (`fleetSurface`) are flaky in both trees
- [x] 4.2 A live rescan on this machine, the expired session measured again [REQ: the-browser-sessions-can-be-rescanned-from-the-strip] — 2026-11-08: `POST /api/usage/accounts/rescan` took 4.3 s, found 3 sessions, the expired browser session measured again (weekly 45 %), store mode 664 → 600, the log line carries counts only
- [x] 4.3 Visual check in Chrome of the header and the detail [REQ: the-claude-pool-reads-the-week-against-the-time-that-has-passed] — 2026-11-08: header reads `Claude ▬ 192% <a> ▬ <b> ▬ GLM ▬ ChatGPT ▬ ?1`, the pool amber; its title names the left-out team account. Detail: the merged row says `Claude Code + browser session`; pressing "rescan Chrome sessions" answered `found 3: …` in place; the panel floated, the header did not move

## Acceptance Criteria (from spec scenarios)

- [x] AC-1 Two emails on one domain get `acme` and `acme team` [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [x] AC-2 One subscription reached two ways is one mark, its row naming both kinds [REQ: the-strip-belongs-to-the-header-because-the-quota-is-not-a-per-agent-fact]
- [x] AC-3 20 %/50 % and 60 %/40 % pool to 40 % over 45 % and read 89 % [REQ: the-claude-pool-reads-the-week-against-the-time-that-has-passed]
- [x] AC-4 A subscription without figures is left out and named [REQ: the-claude-pool-reads-the-week-against-the-time-that-has-passed]
- [x] AC-5 Above 100 % is amber, never critical red [REQ: the-claude-pool-reads-the-week-against-the-time-that-has-passed]
- [x] AC-6 A rescan brings an expired session's bars back at once [REQ: the-browser-sessions-can-be-rescanned-from-the-strip]
- [x] AC-7 A scan that cannot run says so and removes nothing [REQ: the-browser-sessions-can-be-rescanned-from-the-strip]
- [x] AC-8 Fresh cookies replace expired ones, mode 0600; a manual entry survives [REQ: a-rescan-replaces-scanned-sessions-and-keeps-manual-ones]
- [x] AC-9 The answer names the sessions and carries no cookie; a second press answers 409 [REQ: the-rescan-measures-again-and-answers-without-secrets]
- [x] AC-10 A dangling keyring item does not stop the password lookup [REQ: the-keyring-password-is-found-despite-a-broken-item]
