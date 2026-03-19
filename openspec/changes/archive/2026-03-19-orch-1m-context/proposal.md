## Why

The wt-tools orchestration system's context injection was designed for 200K windows — everything is truncated, keyword-matched, and narrowed. With Claude Opus 1M context available, the constraint shifts from "fit in window" to "maximize signal quality." Meanwhile, the `data-definitions.md` digest file actively teaches agents wrong field names (e.g., `shipping_address` instead of `addressId`, `total` instead of `totalAmount`), directly causing schema naming drift that burns retry cycles.

## What Changes

- **Fix the data-definitions digest**: Replace the stale LLM-generated entity summary with an auto-generated schema digest parsed directly from `prisma/schema.prisma` (or equivalent ORM schema), eliminating naming drift at the source
- **Add read-first and conventions instructions**: Inject brief "read before writing" directives and project convention summaries into dispatch context so agents follow established patterns on first attempt
- **Restructure retry context**: Replace truncated raw review/build/test output with parsed, structured retry blocks that preserve all actionable information instead of cutting mid-issue at 1500 chars
- **Add cross-cutting file strategy**: Introduce i18n sidecar pattern and cross-cutting file ownership to prevent the #1 source of merge conflicts (11 files with unresolved markers in a single commit during craftbrew-run2)

## Capabilities

### New Capabilities
- `schema-digest-generation`: Auto-parse ORM schema files at dispatch time and inject accurate model/field/relation/enum data into worktree CLAUDE.md, replacing the stale `data-definitions.md`
- `dispatch-conventions`: Inject read-first instructions and project conventions document into dispatch context to reduce first-attempt errors
- `structured-retry-context`: Parse build errors, test failures, and review issues into structured FILE:LINE:FIX blocks with severity, replacing truncated raw dumps in retry prompts
- `cross-cutting-file-strategy`: i18n sidecar pattern (per-feature namespace files merged at build time) and planner-level cross-cutting file ownership to prevent merge conflicts

### Modified Capabilities
_(none — these are all new orchestration capabilities, no existing specs are changing)_

## Impact

- **dispatcher.py**: New `append_schema_digest_to_claudemd()` function, enhanced `_build_input_content()` with conventions/read-first sections, sidecar file instructions in dispatch context
- **verifier.py**: New `_extract_build_errors()` and `_extract_test_failures()` parsers, refactored `_build_review_retry_prompt()` to use structured format instead of truncated raw output, increased state storage limits
- **planner.py**: Cross-cutting file ownership assignment, `depends_on` for non-splittable shared files
- **merger.py**: Post-merge i18n sidecar combination script trigger
- **digest.py**: Schema digest generation replacing `data-definitions.md` pipeline
- **Consumer projects**: i18n message loading changes (runtime merge of namespace partials), merge script addition
