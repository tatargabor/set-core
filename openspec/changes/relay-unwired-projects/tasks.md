## 1. Core (lib/set_orch)

- [x] 1.1 `unwired_projects()` in `fleet/question_relay.py`: project, local and user settings; matcher must cover AskUserQuestion; unparseable counts as unwired; archived and missing paths skipped [REQ: the-header-names-the-projects-the-relay-cannot-reach]
- [x] 1.2 `unwired` in the relay payload, a scan failure logged and rendered as an empty list [REQ: the-header-names-the-projects-the-relay-cannot-reach]
- [x] 1.3 Unit tests over temp projects (`tests/unit/test_question_relay_unwired.py`) [REQ: the-header-names-the-projects-the-relay-cannot-reach]

## 2. Web

- [x] 2.1 `RelayState.unwired`, lenient parse, `showUnwired`, title that does not call an on-but-bypassed relay calm [REQ: the-header-names-the-projects-the-relay-cannot-reach]
- [x] 2.2 Closed-header marker and the list in the relay detail (`FleetRelay.tsx`) [REQ: the-header-names-the-projects-the-relay-cannot-reach]
- [x] 2.3 Unit tests in `web/tests/unit/fleetRelay.test.ts` [REQ: the-header-names-the-projects-the-relay-cannot-reach]
- [x] 2.4 Visual check of the header and the detail in the browser (ui-quality rule) [REQ: the-header-names-the-projects-the-relay-cannot-reach]
      Done 2026-11-17 after a rebuild and a set-web restart: the closed header shows an amber warning with 3 beside the relay switch; clicking it opens the detail floating over the page (nothing below moved), listing three registered projects, each "missing set-hook-question-relay, set-hook-wait-detect".
