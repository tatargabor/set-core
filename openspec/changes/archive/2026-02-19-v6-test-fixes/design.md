## Context

Benchmark v6 showed both runs completing 12/12 changes with 0 test-fix cycles, but Run A outscored Run B on C12 bugs (11 vs 9) and drift traps (2/2 vs 1.5/2). Post-run investigation revealed the test suite is too weak — test-12 passes 71% of checks without a server running. Code map coverage regressed from 4/12 to 2/12 because the hook's safety-net is gated behind a design-marker `continue` that prevents re-evaluation. The memory agent showed 50% token reduction on C12 but lower quality, suggesting overconfidence from recalled-but-unverified code maps.

## Goals / Non-Goals

**Goals:**
- Make test-12 catch the actual failures observed in v6 (payout untested, Pagination import-only, Toast non-global, vendor skipped)
- Ensure code map generation fires for every change commit, not just the first
- Add recall-then-verify instruction to reduce memory-induced overconfidence
- Isolate memory databases between benchmark runs

**Non-Goals:**
- Rewriting the entire test suite (focus on P0/P1 fixes only)
- Changing the convention extraction prompt or insight extraction logic
- Adding new traps (TRAP-O etc.) — save for v7 design
- Fixing TRAP-G (checkout navigation) — requires change definition update, not test fix

## Decisions

### D1: Payout check — FAIL on missing data vs seed multi-vendor orders
**Choice**: FAIL when `no_multi_vendor_orders` with a clear note. Creating test seed data adds complexity (needs 3+ vendors, multi-vendor cart, checkout) and couples the test to seed correctness. A FAIL with a note is simpler and forces the agent to implement proper seed data.
**Alternative**: Add a test setup block that POSTs multi-vendor orders via API. Rejected — test scripts should validate, not create state.

### D2: TRAP-M — JSX render check approach
**Choice**: Use `grep -E "<Pagination|<Pagination " "$PAGE_FILE"` to match JSX render syntax. This catches `<Pagination />`, `<Pagination page={...}` etc. while excluding `import { Pagination }` or `// Pagination`.
**Alternative**: Use `grep "from.*Pagination"` to only check imports. Rejected — that's the current behavior and is insufficient.

### D3: TRAP-N — Global mount check
**Choice**: Add a separate check that `layout.tsx` (root layout) contains `Toast` or `Toaster` reference. This validates the "mount once globally" architecture pattern.
**Alternative**: Check every page file doesn't have `<Toast`. Rejected — false negatives if the component has a different wrapper name.

### D4: Code map — restructure vs duplicate
**Choice**: Move the code-map block in `wt-hook-memory-save` outside the `$DESIGN_MARKER` `continue` guard. The code-map already has its own marker (`$CODEMAP_MARKER`) so the design-marker gate is redundant for it.
**Alternative**: Duplicate the code-map block before the continue. Rejected — code duplication.

### D5: Memory DB isolation — project name approach
**Choice**: Use `--project-name` or environment variable in init scripts to make set-memory use `craftbazaar-baseline` vs `craftbazaar-memory` as storage names. This ensures physically separate databases.
**Alternative**: Use `--db-path` to point to run-specific directories. Rejected — more invasive, requires all memory commands to pass the path.

## Risks / Trade-offs

- [Risk] Payout FAIL may cause both runs to fail test-12 if neither seeds multi-vendor orders → Mitigation: The test note is clear about what's needed; agents should create proper seed data in C12 sprint retro.
- [Risk] `grep "<Pagination"` may miss JSX spread patterns like `{...Pagination}` → Mitigation: This edge case is unlikely in the benchmark context; standard JSX render is the target.
- [Risk] Code-map unconditional generation may create duplicate code maps if both design-marker AND code-map-marker paths fire → Mitigation: The code-map-marker check (`$CODEMAP_MARKER`) prevents duplicates regardless of entry path.
