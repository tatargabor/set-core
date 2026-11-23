## Context

Next.js App Router enforces a server/client boundary. A file marked `"use client"` becomes a Client Component module — everything it exports is wrapped in a Client Component reference, including plain functions. When a server module (no `"use client"` directive) imports and **calls** a function from a client module, the build succeeds but at request time Next throws:

```
Attempted to call parseSelectorVariants() from the server but
parseSelectorVariants is on the client.
```

This failure mode is invisible to `next build` and invisible to unit tests. It only surfaces when the page is requested — at which point all e2e tests targeting that page fail with an Application Error shell. In `craftbrew-run-20260423-2223` this class of bug cost ~8 hours: 10 e2e failures → smoke gate retry exhaustion → fix-iss children spawned → token_runaway spiral → change abandoned.

The web profile already registers 4 gates (`i18n_check`, `e2e`, `lint`, `design-fidelity`) via `register_gates()` in `modules/web/set_project_web/project_type.py`. Adding one more is a well-trodden path.

## Goals / Non-Goals

**Goals:**
- Detect server-to-client function/const/enum imports **before build** so the agent gets a precise, line-accurate error instead of a white Application Error page.
- Zero new runtime dependencies — pure-Python AST or text-parse over `.ts`/`.tsx` files.
- Actionable `retry_context` for the agent: file, line, imported symbol, source module.
- ≤300ms on a 2000-file scaffold; no subprocess, no network.

**Non-Goals:**
- Full TypeScript type-checking or module resolution with path aliases. The gate reuses the project's tsconfig `baseUrl` + `paths` only to resolve `@/…` imports; complex aliases or `.d.ts`-only modules are skipped with a debug log.
- Catching the inverse direction (client importing server-only code). `server-only` package already enforces this at build time in Next.js.
- Enforcing the rule on files outside `src/` (e.g., `tests/`, `scripts/`). Those have no client/server boundary in Next App Router.
- Replacing or subsuming `lint` gate. ESLint can be extended later with a plugin for the same rule; this gate is the fast orchestration-layer check.

## Decisions

### Decision 1: Text-based import parser, not full TypeScript AST

The gate extracts imports with a **tight regex** over the first ~200 lines of each `.ts`/`.tsx` file: `import ... from "..."`, `import type ...`, `"use client"` / `"use server"` directive detection.

**Why:** Full TS AST needs `tree-sitter-typescript` or `libcst-ts` — new native deps or bundled grammars. The regex handles 99%+ of real-world Next.js imports (no exotic formatting) and runs at ~1ms/file. Edge cases (multi-line imports, comments inside import lists) are handled by a small state machine, not full parsing.

**Alternatives considered:**
- `tree-sitter-typescript` (rejected: new native dep, build complexity)
- `swc` via subprocess (rejected: 50ms/file startup, kills the "fast gate" goal)
- ESLint rule (rejected: needs project-specific ESLint config, consumer burden; plus ESLint typically runs AFTER build in our pipeline)

### Decision 2: Resolution via tsconfig `paths`, fallback to relative-only

The gate parses the consumer's `tsconfig.json` once per run to get `compilerOptions.paths` (e.g., `"@/*": ["./src/*"]`). Resolution order for an import target:
1. Relative (`./`, `../`) → resolve against importer's directory.
2. Alias-matched (`@/foo` → `src/foo`) → resolve against project root.
3. Bare (`next`, `react`, `sonner`, etc.) → skip (not our source files).

After resolution, check `.tsx` first, then `.ts`, then `index.tsx`, then `index.ts`.

**Why:** This matches what Next.js/Webpack resolves. Missing alias or broken tsconfig → log a WARNING and skip the file; never fail the gate on our own resolution limits.

### Decision 3: What counts as a VIOLATION

Given a server file (no `"use client"`) importing from a client file (has `"use client"`):

| Import form | Status | Reason |
|---|---|---|
| `import { Button } from "./client-mod"` | allowed | Capitalized = JSX component |
| `import { parseX } from "./client-mod"` | **VIOLATION** | lowercase = function/const/enum |
| `import type { Props } from "./client-mod"` | allowed | type-only, erased at compile |
| `import { type Props, Button } from "./client-mod"` | allowed (component) | type inline-erased; component OK |
| `import { type Props, parseX } from "./client-mod"` | **VIOLATION** | parseX flagged |
| `import Button from "./client-mod"` | allowed | default import, assumed component |
| `import * as lib from "./client-mod"` | **VIOLATION** | namespace import may reach any export |
| `import "./client-mod"` | allowed | side-effect-only, fine |

Capitalized identifier = `^[A-Z]` (React convention). Lowercase = function/const by convention. Edge case: type-exported enums (`export enum Foo`) named PascalCase look like components — false-negative acceptable, the enum isn't call-shaped at a JSX site.

### Decision 4: Gate position and failure mode

- **Position:** `position="before:build"`. The gate must run before `build` because when it fails, rebuilding or running e2e is wasted work. Before `build` in the web pipeline currently means the gate runs first among the web-registered gates.
- **Phase:** `verify` (same as `lint`, `test`, `e2e`). Does NOT run on integration — the check is deterministic per commit; if verify passed, integration is a no-op.
- **Defaults:** run on `foundational` and `feature` change types; skip on `infrastructure`, `schema`, `cleanup-before`, `cleanup-after` (those don't touch render code).
- **Result fields:** `client_boundary_result` ∈ {`pass`, `fail`} + `gate_client_boundary_ms`.
- **Retry policy:** cheap (re-runs fully on retry), no caching.

### Decision 5: Retry context format

On failure, emit a structured message that the agent can fix deterministically:

```
CLIENT BOUNDARY VIOLATIONS (N files, M imports):

src/components/catalog/detail/product-detail-layout.tsx:13
  import { parseSelectorVariants } from "./variant-selector"
  → variant-selector.tsx is a "use client" module; parseSelectorVariants
    is a plain function, not a component.
  FIX: move parseSelectorVariants to a new non-"use client" module
       (e.g. ./variant-selector-types.ts) and import it from there in
       both the server layout AND the client variant-selector.

src/app/[locale]/(shop)/kavek/[slug]/page.tsx:5
  import { helper } from "@/lib/client-utils"
  → client-utils is a "use client" module; helper is a function.
  FIX: (same pattern) extract helper into a server-safe module.
```

Structured fields in state: `client_boundary_violations: list[dict]` with `{file, line, import, target_module, symbol}`.

## Risks / Trade-offs

- **Regex-based parsing misses exotic syntax** → Mitigation: bail-out to per-file WARNING log and treat the file as "unanalyzed" rather than blocking. Track via telemetry; if > 5% of files bail out on any consumer, upgrade to AST parser.
- **False negatives on PascalCase non-component exports** (e.g., enum, class) → Mitigation: documented in rule markdown; real cases are rare and don't cause the runtime error (you'd need to call them server-side to explode).
- **tsconfig alias drift** → Mitigation: gate re-reads tsconfig on every run; WARNING if alias resolution fails, never blocks the gate.
- **Monorepo layout where `src/` is not the web root** → Mitigation: gate walks the project's `app/` and `src/` dirs (both common for Next.js). If neither exists, gate is a no-op with INFO log.
- **Noise on first-run upgrades** (pre-existing violations in a consumer that adopts this gate) → Expected and desirable: the agent fixes them via retry_context. If too noisy, a consumer can add an `.openspec-client-boundary-ignore` file with glob patterns.

## Migration Plan

1. Land in set-core.
2. Deploy to consumer projects via `set-project init` on next registration (new rule markdown + no code change required on consumer side — the gate is framework-level).
3. Existing consumers get the new gate on next `set-web` service restart that reloads the web profile.
4. Rollback: remove the `GateDefinition(...)` entry from `register_gates()`; gate disappears from the pipeline. Zero state migration needed.

## Open Questions

- Should we surface violations in the `lint` gate output too, for IDE ergonomics, even though the dedicated gate is authoritative? (Leaning no — one source of truth; the rule markdown tells developers to look at the gate output.)
- Do we want a `--fix` mode later that auto-extracts server-safe functions into a sibling module? (Out of scope here; could be a follow-up change once we see agent fix-patterns.)
