## Why

In `craftbrew-run-20260423-2223`, `catalog-product-detail` deadlocked for 8+ hours and ultimately died with `failed:token_runaway`. Root cause: a single server component imported a plain function from a `"use client"` file (`ProductDetailLayout` → `parseSelectorVariants` in `variant-selector.tsx`). Next.js builds this silently, then throws `Attempted to call X() from the server but X is on the client` at every request — all 10 e2e tests see an Application Error page, smoke gate exhausts its retry budget, fix-iss children spawn, and the agent loop burns tokens on a deterministic bug it cannot reason about from test output alone.

This is a pre-runtime, AST-detectable class of bug. A fast static gate eliminates entire failure modes before any build or test runs.

## What Changes

- Add a new web-profile gate `client-boundary` that scans `.ts`/`.tsx` under `src/` and flags any server module (no `"use client"` directive) that imports a **non-component, non-type** symbol from a `"use client"` module.
- Gate runs **before build** in the web profile pipeline; typical cost 50–300ms on the scaffold size we ship.
- Failures include file path, line, source module, and offending symbol — formatted for the agent's `retry_context` so the agent can fix it deterministically.
- New consumer-facing rule doc explaining the constraint with good/bad examples, deployed by `set-project init`.

## Capabilities

### New Capabilities
- `client-boundary-gate`: Static analysis gate that prevents server-to-client function imports in Next.js App Router projects.

### Modified Capabilities
- `web-gates`: Registers the new `client-boundary` gate in the web profile's pipeline at the pre-build position.

## Impact

- **Affected code:** `modules/web/set_project_web/gates.py` (new function), `modules/web/set_project_web/project_type.py` (gate registration), `modules/web/set_project_web/tests/` (unit tests), `templates/core/rules/client-boundary.md` (new rule, deployed to consumer projects).
- **No consumer migration needed:** new gate catches pre-existing violations on first run; agents fix them with the structured retry_context.
- **Perf:** ~50–300ms per gate run on a typical scaffold (500–2000 files). No network, no subprocess — pure Python AST walk.
- **No breaking changes** to existing gates, pipeline ordering, or profile contracts.
