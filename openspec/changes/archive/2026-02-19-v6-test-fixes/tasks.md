## 1. Test-12 Fixes

- [x] 1.1 Fix payout check (Bug 2): change `no_multi_vendor_orders` case from `check ... 'true'` to `check ... 'false'` with FAIL message "No multi-vendor orders — payout algorithm untested"
- [x] 1.2 Fix TRAP-M check (Bug 11): change `grep "Pagination"` to `grep "<Pagination"` for all page file checks to detect JSX render, not just import
- [x] 1.3 Fix TRAP-N check (Bug 12): add new check that `src/app/layout.tsx` contains `Toast` or `Toaster` reference for global mount verification
- [x] 1.4 Fix vendor regression: replace silent skip (`if [ -n "$VENDOR_DASH_ID" ]; then ... fi`) with explicit FAIL when no vendor ID obtained

## 2. Change Definition Fixes

- [x] 2.1 Update `benchmark/changes/12-sprint-retro.md` Bug 11 acceptance criteria: add "Pagination must be rendered (`<Pagination .../>`) on all list pages, not just imported"
- [x] 2.2 Update `benchmark/changes/12-sprint-retro.md` Bug 12 acceptance criteria: add "Toast/notification component must be mounted once in `src/app/layout.tsx` for global availability"
- [x] 2.3 Update `benchmark/changes/02-shopping-cart.md` acceptance criteria: add "Cart page must include a 'Proceed to Checkout' button/link that navigates to `/checkout`"
- [x] 2.4 Add checkout link check to `benchmark/tests/test-02.sh`: verify cart page contains href to /checkout

## 3. Memory Save Hook

- [x] 3.1 Move code-map block in `bin/wt-hook-memory-save` outside the design-marker `continue` guard so it fires for every commit independently

## 4. CLAUDE.md Template

- [x] 4.1 Add recall-then-verify paragraph to `benchmark/claude-md/with-memory.md` Proactive Memory section: "After recalling code maps or implementation details, ALWAYS grep/verify against current codebase state before acting — memory may be outdated."

## 5. Memory DB Isolation

- [x] 5.1 Update `benchmark/init-with-memory.sh` to use project name `craftbazaar-memory` for set-memory storage (via project directory name or set-memory config)
- [x] 5.2 Verify that init-baseline.sh does NOT install memory hooks (already the case — confirm no regression)
