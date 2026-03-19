## Context

The set-core orchestration pipeline (dispatcher, verifier, merger, planner in `~/code2/set-core/lib/set_orch/`) injects context into subagent worktrees at dispatch time. Current injection was designed for 200K context windows:

- `data-definitions.md` — LLM-generated entity summary, copied to `.claude/spec-context/` (dispatcher.py:1337-1343)
- `conventions.json` — project conventions, same path
- Review retry prompt — truncates review output to 1500 chars (verifier.py:221)
- Build retry — truncates to last 2000 chars of build output
- No cross-cutting file coordination between parallel agents

With 1M context now available, the bottleneck is signal quality, not window size.

## Goals / Non-Goals

**Goals:**
- Eliminate schema naming drift caused by stale `data-definitions.md`
- Reduce first-attempt failures via conventions and read-first instructions
- Improve retry convergence by preserving all actionable review/build/test feedback
- Reduce merge conflicts on shared files (i18n JSON, layout.tsx, middleware.ts)

**Non-Goals:**
- Cacheable common prefix (not controllable via CLI)
- LLM-based context selection (non-deterministic, unnecessary with 1M)
- Full spec mesh injection (phantom dependency risk)
- Raw retry dump without structure (sunk cost bias)

## Decisions

### D1: Replace data-definitions.md with auto-parsed schema digest

**Choice:** Parse `prisma/schema.prisma` (or detected ORM schema) at dispatch time, generate a `## Project Schema (auto-generated, readonly)` section appended to worktree CLAUDE.md.

**Why not keep data-definitions.md?** It actively teaches wrong field names. The current file says `shipping_address` (actual: `addressId`), `total` (actual: `totalAmount`), `label`/`is_default` on Address (don't exist). Agents learn from this file and produce code that fails at build time.

**Why CLAUDE.md not spec-context?** CLAUDE.md is always loaded by Claude. Spec-context files can be ignored. Following the `append_startup_guide_to_claudemd()` pattern (dispatcher.py:481-511).

**Why parse, not LLM-generate?** Parsing is deterministic — zero chance of name drift. The schema file is the single source of truth.

**Alternatives rejected:**
- Fix data-definitions.md manually → goes stale again after schema changes
- Inject full schema.prisma → too large for non-Prisma projects, no filtering

### D2: Inject conventions + read-first instructions at dispatch

**Choice:** Add two small sections to dispatch context:
1. **Read-first instruction** (~100 bytes): "Before writing Prisma code, read prisma/schema.prisma. Before creating components, check src/components/."
2. **Conventions document** (~500 bytes): Auth patterns, i18n namespacing, CSS approach, component reuse rules. Detected from `package.json` dependencies + conventions.json.

**Why in dispatch context, not CLAUDE.md?** These are change-specific instructions. CLAUDE.md is project-wide. The dispatcher's `_build_input_content()` (line 817) is the right injection point.

**Alternatives rejected:**
- Full reference implementation injection (30-80K) → agents can read files themselves; read-first instruction achieves 95% of the value

### D3: Structured retry context replacing truncated raw dumps

**Choice:** Three-part refactor of retry prompts:

1. **Remove raw review output from retry prompt** — line 221 (`current_review_output[:1500]`) is redundant when `_extract_review_fixes()` already provides structured data. Only include raw output as fallback when parser finds zero issues but `has_critical` is True (increase to `[:3000]` in that case).

2. **Add build error parser** — new `_extract_build_errors()` function extracting `file:line: TS####: message` tuples from TypeScript/Next.js output (same pattern as `_extract_review_fixes()`).

3. **Add test failure parser** — new `_extract_test_failures()` function extracting failed test names + assertion details from Jest/Vitest output.

4. **Unified retry format** — single `_build_unified_retry_context()` combining all gate results:
   ```
   ## Retry Context (Attempt N/M)
   ### Build Errors
   - src/file.tsx:67 — TS2339: Property 'total' does not exist
   ### Review Issues
   - [CRITICAL] src/file.tsx:45 — Missing auth check
     FIX: Add getServerSession() guard
   ### Test Failures
   - checkout.test.ts: "should calculate shipping" — Expected 1500 received undefined
   ```

5. **Add re-read instruction** to retry prompt: "Before fixing, re-read the files listed above. Do NOT rely on your memory of the file contents."

**Why not track "resolved vs still-open"?** The review runs fresh each attempt — the current output already tells you what's still open. Diffing across attempts by line number is fragile (code shifts). Unnecessary complexity.

**Alternatives rejected:**
- Full raw dump (60-90K) → sunk cost bias, noise overwhelms signal
- "Resolved" detection → unnecessary when review re-runs fresh each time

### D4: Cross-cutting file strategy — i18n sidecar + ownership

**Choice:** Two mechanisms:

1. **i18n sidecar pattern**: Agents write to `src/messages/en.<feature>.json` (or `src/i18n/messages/partials/<locale>.<feature>.json`). A post-merge script combines partials into the canonical file. Each partial owns top-level namespaces — `Object.assign` at top level, no deep merge needed. Namespace collisions are caught at dispatch time (planner assigns namespaces).

2. **Cross-cutting file ownership**: Planner explicitly marks which change "owns" unsplittable files (layout.tsx, middleware.ts, next.config.js). Other changes get a `depends_on` on those files, forcing serialization at dispatch level. Non-owners get "DO NOT modify [file]" in their dispatch context.

**Why not registry pattern (extract data from structural files)?** That's a project-level refactor (moving navLinks to config, extracting providers). The orchestrator shouldn't restructure the target project's architecture — it should work with whatever architecture exists. The sidecar pattern works without project changes for JSON files; ownership works without project changes for structural files.

**Alternatives rejected:**
- Full sidecar for all files → only works for ~2 of 8 conflict-prone file types
- Rebase-before-merge → agents resolving their own conflicts during rebase is promising but higher risk, consider for future iteration

## Risks / Trade-offs

- **[Risk] Schema parser only supports Prisma initially** → Mitigation: detect ORM from dependencies (package.json, requirements.txt), start with Prisma, add Django/SQLAlchemy/TypeORM later via parser registry
- **[Risk] i18n sidecar breaks dev hot-reload** → Mitigation: merge script runs on file watch in dev mode, or use runtime `import.meta.glob` merge in the message loader
- **[Risk] Conventions document goes stale** → Mitigation: auto-detect from package.json (framework versions, auth lib), supplement with conventions.json from digest
- **[Risk] Build error parser doesn't cover all build tools** → Mitigation: start with TypeScript/Next.js (covers craftbrew), add parsers for Vite, webpack, etc. iteratively. Fall back to truncated raw output for unknown formats.
- **[Risk] Ownership serialization reduces parallelism** → Mitigation: only serialize truly unsplittable files (layout.tsx, middleware.ts), most changes don't touch these

## Open Questions

1. Should the schema digest include sample data / seed values, or just structure?
2. For non-Prisma projects, what's the minimum viable parser? (TypeORM entities? Django models.py?)
3. Should the i18n merge happen at build time (simpler) or runtime via import.meta.glob (no build step)?
