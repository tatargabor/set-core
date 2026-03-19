# Plan Review Checklist

Quick pre-flight check before running `set-orchestrate start`. Review the plan (`set-orchestrate plan --show`) against this list.

> Full explanations: [Planning Guide](planning-guide.md)

---

## Scope & Overlap

- [ ] **No shared files in parallel changes** — If two changes edit the same file (types, config, schema, barrel exports), one depends on the other
- [ ] **Each scope is self-contained** — Can be described in 2-3 sentences without "and also"
- [ ] **No L-sized changes** — Changes with 25+ estimated tasks should be split into M-sized pieces
- [ ] **Scope descriptions are specific** — Include constraints, tech choices, and boundaries (not just "add feature X")

## Dependencies

- [ ] **Schema migrations are sequential** — Only one change creates Prisma migrations; others depend on it
- [ ] **Auth is foundational** — Auth/authorization changes are early dependencies, not parallel work
- [ ] **Shared type changes extracted** — If multiple changes add to the same union type/enum, extract a shared change
- [ ] **No circular dependencies** — A depends on B which depends on A (the validator catches this, but check anyway)
- [ ] **Package.json conflicts considered** — Multiple changes adding different npm packages should be chained
- [ ] **Cleanup/refactor runs before features** — If a cleanup change touches the same area as feature changes, features should depend on the cleanup
- [ ] **Change types considered** — Each item classified as infrastructure, schema, foundational, feature, or cleanup; ordering follows naturally from type

## Testing

- [ ] **Test requirements specified** — Each change scope mentions what to test (happy path, error cases)
- [ ] **Test infrastructure exists or is first change** — If no test setup, first change must be `test-infrastructure-setup`
- [ ] **Existing patterns referenced** — If project has tests, spec mentions framework and conventions
- [ ] **Functional e2e for UI features** — Changes with forms/CRUD/flows include `Functional:` line with spec file path
- [ ] **Smoke updates for new routes** — Changes adding new pages include smoke navigation update
- [ ] **Three-layer separation clear** — Unit tests validate logic, e2e validates feature flow, smoke validates navigation

## Sizing & Phases

- [ ] **Batch size is 4–6 changes** — Fewer underutilizes parallelism; more risks merge conflicts
- [ ] **Phases marked if >6 changes total** — Use `## Phase N` headers for multi-batch work
- [ ] **Each phase is independently valuable** — Phase 1 results should be usable before Phase 2 starts

## Directives

- [ ] **`max_parallel` set appropriately** — 2-3 for complex changes, 3-4 for simple/isolated ones
- [ ] **`merge_policy` chosen** — `eager` for sequential auto-merge, `checkpoint` for review between merges, `manual` for full control
- [ ] **`test_command` set** — Points to your project's test runner (e.g., `pnpm test`)
- [ ] **`auto_replan` considered** — Set to `true` for multi-phase specs if you want hands-off execution
- [ ] **`default_model` considered** — Set to `sonnet` for cost-sensitive batches; default is `opus`
- [ ] **Per-change `model` set where needed** — S-complexity cleanup/doc changes can use `sonnet`; complex features should use `opus`
- [ ] **`post_merge_command` set if needed** — Project-specific command after merge (e.g., `pnpm db:generate` for Prisma)
- [ ] **`skip_review`/`skip_test` for doc-only changes** — Doc changes that don't touch code can skip test and review gates

## Runtime & Post-Merge

- [ ] **Runtime dependencies explicit** — If a feature needs a new npm package, mention it in scope (build passes in worktree but main may lack it after merge)
- [ ] **Error handling for missing data** — Features that query DB records should handle "not found" cases (agents often skip existence checks before `.update()`)
- [ ] **Feature completeness verifiable** — Each scope item has clear acceptance criteria so you can verify nothing was silently dropped by the agent
- [ ] **Generated file conflicts expected** — `.claude/reflection.md` and similar AI-generated files will conflict on every merge; ensure they're in `set-merge`'s `GENERATED_FILE_PATTERNS`
- [ ] **Shared type accumulation considered** — If 3+ changes add to the same union type, later merges get progressively harder; extract a shared-types change or chain all of them

## Web Project Specifics

- [ ] **Tech stack documented** — Framework, ORM, CSS, component library specified in spec
- [ ] **DB access patterns clear** — ORM vs raw SQL, tenant isolation approach, migration strategy
- [ ] **Auth approach specified** — JWT/session, role model, middleware location
- [ ] **Deployment platform noted** — Build command, runtime constraints, env var management
- [ ] **Env vars listed** — Required environment variables documented for each feature
