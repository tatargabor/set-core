## 1. Phase 0 — Immediate Fix (data-definitions + conventions)

- [x] 1.1 Stop copying `data-definitions.md` to worktrees: remove from dispatcher L1342 copy loop AND skip in planner L983 data model injection. Unconditional removal (task 2 adds the replacement).
- [x] 1.2 Add `read_first_directives: list[str]` and `conventions_summary: str` fields to `DispatchContext`. Populate in `_setup_change_in_worktree()` by detecting `prisma/schema.prisma`, `src/components/`, etc. in `wt_path`. Inject in `_build_input_content()` via ctx.
- [x] 1.3 Add conventions injection: read `conventions.json` from `digest_dir`, format as compact markdown (~500 bytes), set `ctx.conventions_summary`. Inject in `_build_input_content()`. Keep spec-context copy as secondary channel.
- [x] 1.4 Write unit tests for read-first and conventions injection (mock project structure, verify output contains expected directives)

## 2. Schema Digest Generation

- [x] 2.1 Create `parse_prisma_schema()` function in a new `dispatcher_schema.py` module: parse model names, field names+types, relations, enums from `prisma/schema.prisma` using regex (not Prisma CLI dependency)
- [x] 2.2 Create `format_schema_digest()` function: convert parsed schema into concise markdown (model → fields table, relations list, enum values)
- [x] 2.3 Create `append_schema_digest_to_claudemd()` function following `append_startup_guide_to_claudemd()` pattern: idempotent, creates CLAUDE.md if missing, replaces existing `## Project Schema` section if present
- [x] 2.4 Integrate into dispatch flow: call `append_schema_digest_to_claudemd()` during worktree setup (after `append_startup_guide_to_claudemd()`, L1220)
- [x] 2.5 Write unit tests: parse real Prisma schema, verify all models/fields/relations/enums extracted; verify CLAUDE.md idempotency

> **Deferred:** Framework detection (NextAuth v4/v5, next-intl, Tailwind version sniffing) moved out — belongs in conventions injection (task 1.3), not schema digest. Will add as separate task if needed.
> **Simplified:** data-definitions.md skip logic removed — task 1.1 already removes it unconditionally.

## 3. Structured Retry Context — Build Error Parser

- [x] 3.1 Create `_extract_build_errors()` function in `verifier.py`: regex-based parser for TypeScript errors (`TS\d{4}`), Next.js module errors, route export violations
- [x] 3.2 Replace raw build output in build retry prompt (verifier.py build failure path) with structured `_extract_build_errors()` output, falling back to `[-3000:]` raw for unknown formats
- [x] 3.3 Write unit tests with sample TypeScript/Next.js build outputs (capture real examples from craftbrew-run2 logs)

## 4. Structured Retry Context — Test Failure Parser

- [x] 4.1 Create `_extract_test_failures()` function in `verifier.py`: parse Jest/Vitest FAIL blocks, extract test name + file + expected/received
- [x] 4.2 Replace raw test output in test retry prompt with structured `_extract_test_failures()` output
- [x] 4.3 Write unit tests with sample Jest/Vitest failure outputs

## 5. Structured Retry Context — Unified Format + Review Fix

- [x] 5.1 Modify `_build_review_retry_prompt()`: remove line 221 (`current_review_output[:1500]`), only include raw fallback when parser returns empty but `has_critical` is True (use `[:3000]`)
- [x] 5.2 Increase review output state storage from `[:2000]` to `[:5000]` in verifier.py review storage path
- [x] 5.3 Create `_build_unified_retry_context()` function: combine `_extract_build_errors()`, `_extract_test_failures()`, and `_extract_review_fixes()` into single structured markdown block with per-gate sections
- [x] 5.4 Add re-read instruction to all retry prompt paths: "Before fixing, re-read the files listed above. Do NOT rely on your memory of the file contents."
- [x] 5.5 Wire unified retry context into all three retry paths (build, test, review) replacing ad-hoc prompt construction
- [x] 5.6 Write integration tests: verify unified format output for combined build+review failures, verify re-read instruction present in all paths

## 6. Cross-Cutting File Strategy — i18n Sidecar

- [x] 6.1 Add i18n sidecar detection to dispatcher: detect JSON-based i18n (next-intl, react-intl from package.json), generate sidecar file path instructions for dispatch context
- [x] 6.2 Add namespace assignment to planner: when multiple changes need i18n keys, assign non-overlapping top-level namespaces per change
- [x] 6.3 Create `merge_i18n_sidecars()` utility function: scan for `<locale>.<feature>.json` files, `Object.assign` at top-level into canonical messages file
- [x] 6.4 Integrate `merge_i18n_sidecars()` into merger post-merge sequence (after branch merge, before build verify)
- [x] 6.5 Write unit tests: sidecar merge with non-overlapping namespaces, namespace collision warning, no-sidecar skip

## 7. Cross-Cutting File Strategy — Ownership + Serialization

- [x] 7.1 Add cross-cutting file detection to planner: read from `project-knowledge.yaml` `cross_cutting_files` list, or detect heuristically from orchestration history
- [x] 7.2 Add ownership assignment to planner: when multiple changes touch the same unsplittable file, assign one owner and add `depends_on` to others
- [x] 7.3 Add "DO NOT modify" instruction to dispatch context for non-owned cross-cutting files
- [x] 7.4 Add `depends_on` enforcement in dispatcher: serialize dispatch of changes that depend on cross-cutting file owners
- [x] 7.5 Write unit tests: single-owner assignment, depends_on generation, non-owner dispatch context contains prohibition
