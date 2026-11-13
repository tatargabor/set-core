## 1. CLI

- [x] 1.1 `reviewed` writes `{at}` only; `_drop_by` also drops a legacy `reviewed.by` [REQ: an-agent-can-record-that-a-board-was-reviewed]
- [x] 1.2 `sync` state and combined payloads, and the combined seed, without `synced_by` [REQ: sync-is-idempotent-and-writes-the-database-payload]
- [x] 1.3 Unit tests: payload key set without `synced_by`; `reviewed` has no `by`, legacy one dropped; each fails against the old code [REQ: sync-is-idempotent-and-writes-the-database-payload]

## 2. Pages

- [x] 2.1 `page.html` "blocks" tooltip and `combined.html` sync line render no machine [REQ: sync-is-idempotent-and-writes-the-database-payload]
- [x] 2.2 Visual check of both pages in the browser (ui-quality rule); if the browser cannot be reached, this stays open and is said so [REQ: sync-is-idempotent-and-writes-the-database-payload]
      Done 2026-11-13: board page "blocks" tooltip reads "Read from the boards at the last sync.", the sync line has no machine; combined page sync line reads "rendered just now". Both pages rendered with `render` / `combined-page`, served on localhost, opened in Chrome.
