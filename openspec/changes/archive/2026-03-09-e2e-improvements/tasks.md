## 1. Token Scoping Fix

- [x] 1.1 In `gui/usage_calculator.py`: (a) add optional `project_dir: Optional[str] = None` parameter to `UsageCalculator.__init__()`, (b) when set, `iter_jsonl_files()` only yields JSONL files from `~/.claude/projects/<project_dir>/`, (c) change `session_dir.glob('*.jsonl')` to `session_dir.rglob('*.jsonl')` to include subagent session subdirectories.
- [x] 1.2 In `bin/wt-usage`, add `--project-dir` CLI argument. Pass it through to `UsageCalculator(project_dir=args.project_dir)` if set.
- [x] 1.3 In `lib/loop/state.sh` `get_current_tokens()`, derive project dir from `$PWD`: encode as Claude does (replace `/` with `-`, strip leading `-`). Pass `--project-dir <derived>` to `wt-usage`. If dir doesn't exist under `~/.claude/projects/`, log warning to stderr and fall back to unfiltered.
- [x] 1.4 Verify `get_current_tokens()` fallback: when `wt-usage` is unavailable, the existing `estimate_tokens_from_files()` in `lib/loop/state.sh` should return a non-zero estimate. Confirm this works or fix if broken.
- [x] 1.5 Verify: run `wt-usage --since <time> --project-dir <name> --format json` for a known project dir, confirm it only counts that project's tokens.

## 2. Scaffold = Spec Only

Design pivot: the scaffold is a single file (`docs/v1-minishop.md`). Agents build everything from the spec. Platform configs/rules come from `set-project init --project-type web --template nextjs`.

- [x] 2.1 Delete all scaffold files except `docs/v1-minishop.md`: remove `package.json`, `prisma/`, `.env.example`, `.gitignore`, and any remaining config/source files.
- [x] 2.2 Update `v1-minishop.md` to be fully self-contained: add Prisma schema description (models with field names, types, relations), seed data specification, dependency list, and remove redundant convention sections that duplicate `set-project-web` rules.
- [x] 2.3 In `v1-minishop.md`: specify no `.env` file needed — SQLite uses hardcoded `file:./dev.db` in Prisma schema, NextAuth secret uses dev default in code (`process.env.NEXTAUTH_SECRET ?? "dev-secret"`).
- [x] 2.4 Verify `set-project-web` nextjs template is installed and `set-project init --project-type web --template nextjs` works on an empty dir.

## 3. Feature Roadmap Spec

- [x] 3.1 Rewrite `tests/e2e/scaffold/docs/v1-minishop.md` with the 6-change roadmap: products-page, cart-feature (server-side cart via Prisma CartItem + UUID session cookie), orders-checkout (depends: cart-feature + products-page), admin-auth (NextAuth v5, admin routes only protected — storefront remains public), admin-products, playwright-e2e. Each section includes routes, acceptance criteria, file paths, and depends_on. Note in admin-auth section: middleware only protects `/admin/*` routes, storefront and cart remain unauthenticated. Orchestrator directives at the bottom. `smoke_command: pnpm test`, `test_command: pnpm test`.

## 4. E2E Runner Update

- [x] 4.1 Rewrite `tests/e2e/run.sh` for new flow: (a) create empty temp dir, (b) copy spec to `docs/`, (c) `git init`, (d) `set-project init --project-type web`, (e) orchestration config, (f) show instructions for `set-sentinel`. Preflight: pnpm, set-project, web plugin, spec file exists.
- [x] 4.2 Report generation handled by `wt-e2e-report` (invoked manually after sentinel completes).

## 5. E2E Report Generator

- [x] 5.1 Create `bin/wt-e2e-report` (bash script, `chmod +x`): reads `orchestration-state.json`, generates `e2e-report.md` with run summary (duration, total tokens, changes count), per-change table (name, status, tokens, duration, tests), timeline, and directives used. Before writing, rename existing `e2e-report.md` to `e2e-report-prev.md`. If prev report exists, include a comparison section (token totals diff).
- [x] 5.2 Add screenshot capture to `wt-e2e-report`: run `pnpm build`, start app (`pnpm start &`), wait for server ready (poll `localhost:3000/api/health`), run the Playwright screenshot script at `tests/e2e/capture-screenshots.ts` (committed in scaffold, invoked via `pnpm exec playwright test capture-screenshots.ts`), kill server. Embed screenshot links in report.
- [x] 5.3 Create `tests/e2e/capture-screenshots.ts` — Playwright script that visits storefront, cart, orders, admin login, admin products pages and saves PNG screenshots to `e2e-screenshots/`. Lives in set-core source (not scaffold); `wt-e2e-report` copies it into the project at runtime.
- [x] 5.4 Add `wt-e2e-report` to `install.sh` scripts list.

## 6. Validation

- [x] 6.1 Verify `set-project init --project-type web --template nextjs` on empty dir: configs deployed, rules in `.claude/rules/`, CLAUDE.md created.
- [x] 6.2 Run `tests/e2e/run.sh` on a fresh dir. Confirm: project init works, orchestration starts, agents can read spec and create project files.
- [x] 6.3 Run full E2E with sentinel. Confirm: 6 changes orchestrated, per-change tokens are realistic (no cross-project inflation), screenshots captured, report generated.
