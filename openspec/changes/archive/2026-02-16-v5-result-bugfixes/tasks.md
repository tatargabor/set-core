## 0. Hook test & pre-flight infrastructure

- [x] 0.1 Create `benchmark/tests/test-hooks.sh` — isolated test script for memory hook fixes. Uses a temp shodh-memory storage dir (not production). Tests:
  - auto_ingest=False: run `set-memory proactive "test"`, assert zero Conversation memories created
  - change: tag: simulate transcript extraction with a known change name, assert output memory has `change:<name>` tag
  - code-map: create fake commits in a temp repo, trigger save hook, assert code-map memory exists
  - convention extraction: verify LLM prompt contains convention extraction section (grep the hook source)
- [x] 0.2 Create `benchmark/preflight.sh` — pre-benchmark infrastructure check. Validates before a multi-hour run:
  - `set-memory health` passes
  - Hooks installed: `.claude/settings.json` contains `wt-hook-memory-save` and `wt-hook-memory-recall`
  - All 12 change files exist: `benchmark/changes/[0-9]*.md` matches 12 files
  - All 12 test scripts exist and are executable: `benchmark/tests/test-[0-9]*.sh`
  - Glob pattern `[0-9]*.md` works (no repeat of v5 `0*.md` bug)
  - `auto_ingest=False` is in `bin/set-memory` proactive function
  - Dev port (3000/3001) is free
- [x] 0.3 Add single-change smoke test mode to `benchmark/tests/test-hooks.sh --smoke`: run C01 (product-catalog) end-to-end with memory enabled, then verify:
  - At least 1 memory saved with `change:product-catalog` tag
  - Zero `Conversation` type memories from proactive-context
  - Code-map memory exists for the change
  - `set-memory stats` shows noise rate < 20%

## 1. Disable proactive-context auto-ingest (P0)

- [x] 1.1 In `bin/set-memory` `cmd_proactive()`, pass `auto_ingest=False` to `m.proactive_context()` call (line ~609)
- [x] 1.2 Verify: run `set-memory proactive "test context"` and confirm no new Conversation memory is created

## 2. Add change: tag to transcript extraction (P0)

- [x] 2.1 In `bin/wt-hook-memory-save` `extract_from_transcript()`, extract first change name from `$change_names` into a variable (e.g., `first_change`)
- [x] 2.2 Prepend `change:$first_change,` to the tags string in the `set-memory remember` call (line ~254) — before `phase:auto-extract`
- [x] 2.3 Handle edge case: if `$change_names` is empty, skip the `change:` tag (don't add `change:,`)

## 3. Convention extraction via LLM prompt (P1)

- [x] 3.1 Add a second extraction section to the LLM prompt (line ~177-207) asking for conventions: "Cross-cutting conventions established in this session that ALL future changes must follow"
- [x] 3.2 Use format `Convention|tags|content` to distinguish from regular insights
- [x] 3.3 Parse Convention lines separately, cap at 2, save as Learning type with `convention` tag
- [x] 3.4 Include `change:$first_change` in convention tags

## 4. Code-map safety net improvements (P1)

- [x] 4.1 In the commit processing loop, collect ALL changed files across all new commits (not just per-commit)
- [x] 4.2 Add fallback change-name detection from `openspec/changes/` directory when commit message parsing gives "general"
- [x] 4.3 Deduplicate changed files list before generating code-map content

## 5. Mid-run convention compliance checks (P1)

- [x] 5.1 Add convention compliance checks to `benchmark/tests/test-04.sh` (discounts-coupons): grep for `.toFixed()` outside `formatPrice.ts` → fail if found (TRAP-H: formatPrice leak)
- [x] 5.2 Add convention compliance checks to `benchmark/tests/test-05.sh` (checkout-orders): verify all list API endpoints return `{ data, total, page, limit }` envelope (TRAP-I: pagination)
- [x] 5.3 Add convention compliance checks to `benchmark/tests/test-08.sh` (images-table): grep product query files for `deletedAt` filter — warn if any product query lacks it (TRAP-K: soft delete)
- [x] 5.4 Add convention compliance checks to `benchmark/tests/test-03.sh` (multi-vendor): check error responses use constants from `errors.ts`, not hardcoded strings (TRAP-J: error codes)
- [x] 5.5 Add a shared `benchmark/tests/lib/check-conventions.sh` helper that all per-change tests can source — avoids duplicating grep patterns across test scripts

## 6. Benchmark TRAP-F fix (P2)

- [x] 6.1 Add explicit acceptance criterion to `benchmark/changes/07-stock-rethink.md`: "Coupon `currentUses` MUST be incremented inside the checkout-confirm transaction, NOT at coupon-apply time"
- [x] 6.2 Add a TRAP-F evaluator note explaining this is a 3-benchmark recurring failure
