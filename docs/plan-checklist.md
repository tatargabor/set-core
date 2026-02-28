# Plan Review Checklist

Quick pre-flight check before running `wt-orchestrate start`. Review the plan (`wt-orchestrate plan --show`) against this list.

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

## Testing

- [ ] **Test requirements specified** — Each change scope mentions what to test (happy path, error cases)
- [ ] **Test infrastructure exists or is first change** — If no test setup, first change must be `test-infrastructure-setup`
- [ ] **Existing patterns referenced** — If project has tests, spec mentions framework and conventions

## Sizing & Phases

- [ ] **Batch size is 4–6 changes** — Fewer underutilizes parallelism; more risks merge conflicts
- [ ] **Phases marked if >6 changes total** — Use `## Phase N` headers for multi-batch work
- [ ] **Each phase is independently valuable** — Phase 1 results should be usable before Phase 2 starts

## Directives

- [ ] **`max_parallel` set appropriately** — 2-3 for complex changes, 3-4 for simple/isolated ones
- [ ] **`merge_policy` chosen** — `eager` for trusted batches, `checkpoint` for review between merges, `manual` for full control
- [ ] **`test_command` set** — Points to your project's test runner (e.g., `pnpm test`)
- [ ] **`auto_replan` considered** — Set to `true` for multi-phase specs if you want hands-off execution

## Web Project Specifics

- [ ] **Tech stack documented** — Framework, ORM, CSS, component library specified in spec
- [ ] **DB access patterns clear** — ORM vs raw SQL, tenant isolation approach, migration strategy
- [ ] **Auth approach specified** — JWT/session, role model, middleware location
- [ ] **Deployment platform noted** — Build command, runtime constraints, env var management
- [ ] **Env vars listed** — Required environment variables documented for each feature
