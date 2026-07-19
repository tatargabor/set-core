# Readiness Plan — Preparing the Consumer for its First set-core Worktree Run

**One-line answer:** Before set-core is let loose, the consumer must (A) expose its existing three-DB / result-file / gate-script automation behind an abstract `contract.yaml` so set-core *delegates* instead of re-implementing the two unsafe paths (live-DB prisma, stdout-scraped e2e), and (B) close the trunk-based→worktree gaps — hooks that re-arm on install, a `DATABASE_URL` pointing at the live-data copy, and missing per-worktree provisioning — since no worktree has ever run on this project.

**Date:** 2026-07-19. **Companion to** `docs/research/final-plan-2026-07-19.md` — this document does **not** supersede it. Final-plan owns the framework-side Phase 0 data-loss fix (`project_type.py:2015`) and the checks-as-gates mechanism; this plan owns the *consumer-side prerequisites* and the *worktree-readiness* audit that must land alongside it.

> Consumer project name, person names, and vendor/integration names are omitted per `CLAUDE.md`. Disposable DB names are shown generically (`…_dev`, `…_e2e`); the untouchable production mirror is "the live-data copy". Consumer evidence is generic relative script paths reproducible from any consumer's tree; set-core evidence is file:line in this repo.

---

## 1. The two-way fit

The wiring bug in the current setup is a single mistake made twice: **set-core owns a concrete decision it cannot safely make.** It authors `prisma db push --accept-data-loss` against a `DATABASE_URL` it cannot prove is disposable, and it scrapes Playwright stdout instead of reading a result file it doesn't control. Both are cases where the *consumer already owns the safer artifact* and set-core reinvented a weaker one.

So the fit is a division of labor:

- **The consumer supplies the decision** — what is disposable, what passed, what must be wired, what debt is allowed. These are project-owned invariants a generic framework physically cannot encode (Layer-1 rules forbid hardcoding `_e2e`).
- **set-core supplies the orchestration** — when to run each op, how to feed a failing gate's stdout back into the agent's `retry_context`, how to serialize merges, how to diff against the main baseline.

Ownership rule of thumb used throughout this document: **if the fix requires knowing something only the project knows (which DB is disposable, which server actions must be reachable, which reporter the harness forces), the consumer owns it. If the fix is about isolation, provisioning, or not honoring a bypass, set-core owns it.**

---

## 2. List A — Add to the consumer base BEFORE set-core

These are the category-(c) automatisms (set-core reimplements them today, less safely) plus the cadence gaps worth closing natively while the surface is being built. "Native-first" means: expose it as a project artifact so set-core reads it, rather than let set-core fall back to its own implementation.

| Item | Why native-first (not set-core's job) | Consumer effort | Prereq or nice-to-have |
|---|---|---|---|
| **DB lifecycle behind `assertDisposable`** — expose `db_reset`/`db_seed` (+ an idempotent `db:provision <target>` / teardown for worktrees) | Only `scripts/lib/db-target.ts` knows which DB is disposable. When set-core owns the command it authors `prisma db push --accept-data-loss` against the verbatim-copied `DATABASE_URL` = the **live-data copy**, bypassing `assertDisposable` *and* the firewall allow-list. A generic framework cannot encode the disposability predicate. | Low — scripts exist; add a provision/teardown target that is idempotent under SIGKILL (worktrees get timeout-killed) | **PREREQUISITE (safety)** — this is the live data-loss path |
| **Normalized machine-readable `test` result** — `results.test` (junit/json), matching the e2e pattern already proven | `vitest run` emits exit-code only. Every time set-core parses human stdout it is one reporter change from a false-green — exactly the live e2e Bug-2 class. The consumer already proved the file-the-producer-writes pattern works for e2e; extend to vitest. | Low — add `--reporter=junit`/json output path | **PREREQUISITE** for a trustworthy test gate |
| **`.e2e/last-run.json` — already done, just declare it** (`{ok,total,passed,failed,flaky,skipped,failures[{file,title,message}]}`, line-free `(file,title)` keys) | The consumer already owns a superior, SIGKILL-safe, reporter-forced-JSON harness. set-core's stdout scraper (`gates.py:861`) reads the forced `--reporter json` as 0/0 and **misfires the crash/OOM retry guard on every green run**. Line-free keys are exactly what the baseline compare needs. | None — file exists; declare it in the contract | **PREREQUISITE** — declaration + framework reader must land together |
| **Register `check-ui-entrypoints.sh` (+ `orderitem-callsites`) under `checks[]`** | Same "built but never mounted" class as set-core's generic `required-components`, but domain-aware: it traces server actions to a rendered page, which the PascalCase-JSX heuristic cannot see and false-positives on. "Which entrypoints must be reachable" is a project invariant. **Cadence win:** it is WARN-only at pre-push today (gap #4); inside the gate ladder it becomes blocking. | Low — add manifest entry | Nice-to-have, high value |
| **Register `check-bug-regression-tests.sh` + `check-adversarial-review.sh` (baselines consumer-owned)** | Both are shrink-only ratchets tied to project data (`data/…`, review-findings workflow). If set-core owned the baseline it would fight the consumer's `data/` on every re-init. set-core *runs* the check and routes the finding to `retry_context`; it must not own the debt ledger. **Cadence win:** closes gap #2 (regression tests are *authored* but never *executed* after writing). | Low — add manifest entries | Nice-to-have, highest upstream-learning value |
| **Run the real `eslint` as the lint gate** (`lint: eslint …`, `--max-warnings=0`) | set-core's "lint gate" is a forbidden-pattern regex scan, not the project's eslint — a different thing entirely. Declaring `lifecycle.lint` makes the real linter a gate. | None — script exists | Nice-to-have |
| **Add a coverage floor** (absent everywhere; `passWithNoTests:true`) | No coverage threshold exists anywhere in the tree (gap #3); the unit net can silently erode or be bypassed by commit-message labeling. set-core can enforce a floor per-change only if the project declares one. | Medium — pick a floor, wire vitest coverage | Nice-to-have (cadence hardening) |

**Common thread:** for the first three, the consumer supplies the decision (what's disposable, what passed) and set-core supplies the orchestration. set-core owning those decisions is precisely what produced the data-loss path and the false-green — the two first-order safety bugs in the current wiring.

---

## 3. List B — Worktree-readiness checklist

The project is **trunk-based**: development happens on `dev`, pushed directly, no feature branches, **no worktree has ever been exercised**. That is the core unknown. The e2e path is already worktree-exemplary (see "What already works"); the hazards live in the three places set-core touches that the e2e harness does *not* mediate — the raw `DATABASE_URL`, the git hooks that re-arm on `pnpm install`, and hardcoded main-checkout paths.

Legend: **[SAFETY]** corrupts live data · **[BLOCKER]** worktree step fails · **[FRICTION]** slow/noisy but completes.

### HARD BLOCKERS

| # | Hazard | Fix | Owner |
|---|---|---|---|
| 1 | **[SAFETY]** Every worktree's `DATABASE_URL` points at the live-data copy. Dispatcher copies `.env` verbatim *and* `config.yaml` `env_vars.DATABASE_URL` injects the base name. `assertDisposable` only engages for `db:reset`/e2e; set-core's `integration_pre_build` runs `prisma migrate deploy`/`db push` **directly** against the raw URL → schema mutation / column drop on the production mirror, while the run goes green. Highest severity. | **set-core (primary):** `integration_pre_build` must never run prisma against the raw copied `DATABASE_URL`; route through a disposable/`_dev` target or skip when the profile exposes a disposable-DB resolver (couples with final-plan Phase 0). **Consumer (defense-in-depth):** in `config.yaml env_vars` set `DATABASE_URL` → `…_dev` **and** add explicit `E2E_DATABASE_URL: …_e2e` (the e2e resolver appends `_e2e` to the base — a `_dev` base would yield a stray `…_dev_e2e`). | both |
| 2 | **[BLOCKER]** `pnpm install` re-arms git hooks. `core.hooksPath=.husky/_` is in shared repo config → applies in every worktree; `.husky/_` is gitignored but regenerated by `prepare: husky` on install. set-core's post-apply auto-commit then fires the lefthook **pre-commit** chain (`eslint --max-warnings=0` on staged files — one warning aborts the commit, plus 4 gates + squawk). Agent writes one lint warning → commit exits non-zero → set-core commit step fails → state desync / retry storm. | **set-core:** run all automated worktree commits with `git commit --no-verify` (or `HUSKY=0`/`LEFTHOOK=0` in the commit env) — gate enforcement is the merge queue's job, not the per-agent commit's. **Consumer (alt):** make lefthook skip on `set/*` branches. | set-core (primary) |
| 3 | **[BLOCKER]** pre-push = full `tsc --noEmit` (minutes) + 12 gates, one of which (`integration-tests`) hits the **real DB against the live copy** (ties to #1). LFS pre-push also needs `git-lfs` on PATH. If set-core ever pushes a worktree branch, the push is blocked or multi-minute-stalled and can mutate the live DB. | **set-core:** `--no-verify`/`LEFTHOOK=0` on automated pushes; prefer merge-queue integration over pushing from worktrees at all. **Consumer:** same branch-skip as #2. | set-core (primary) |

### FRICTION

| # | Hazard | Fix | Owner |
|---|---|---|---|
| 4 | Playwright browsers not installed by `pnpm install` (`postinstall` runs only `prisma generate`). Works today only because browsers sit in the shared global cache `~/.cache/ms-playwright`; a clean/CI worktree fails at browser launch. | set-core: in `integration_pre_build`, when a Playwright config is detected, run `playwright install --with-deps chromium`. Consumer: add to a setup step. | both |
| 5 | Hardcoded main-checkout path in a live hook: `scripts/hooks/domain-brief-hook.sh:21` does `cd <main-checkout> && node …`, wired as a PostToolUse Edit\|Write hook. A worktree agent editing `src/` computes the brief from **main's** tree, not the worktree's. | Consumer: use `$CLAUDE_PROJECT_DIR` / the hook's own cwd instead of the absolute path. | consumer |
| 6 | Other hardcoded absolute paths off the build/test/e2e path (PDF export, stock-import, feature-trace scripts + `config.yaml design_source_path`, `digest/index.json spec_base_dir`). Not blockers, but any change invoking them from a worktree acts on main. | Consumer: relativize / use env. | consumer |
| 7 | Port 3100 hardcoded in `dev: next dev --webpack --port 3100` — the flag overrides set-core's appended `PORT`. If set-core runs `pnpm dev` for a baseline/healthcheck while main's dev server holds 3100 → `EADDRINUSE`. (e2e path is immune — `e2e.ts` grabs a free port; `max_parallel=1` limits collisions.) | Consumer: honor the env — `next dev -p ${PORT:-3100}`. | consumer |
| 8 | Gitignored-but-required dirs absent in a fresh worktree: `.env`, `.next/` (cold-build cost), the PDF output dir, the photos/documents upload dirs. A flow writing a PDF hits `ENOENT`. | Consumer: `mkdir -p` the required data/public dirs at boot / setup step. | consumer |
| 9 | **[security]** Verbatim `.env` copy + `config.yaml env_vars` replicate real prod tokens into every worktree (deploy-platform, VCS, LLM, agent-API, and billing-vendor API keys). Every worktree agent can reach prod services. | set-core: support an allowlist/denylist or redaction of env keys when provisioning a worktree `.env`. Consumer: keep real prod tokens in a separate file not copied into worktrees; keep `.env` mock-only (it already declares no-live-keys yet carries a prod deploy token). | both |
| 10 | `set-hook-*` CLIs must be on the worktree agent's PATH (`.claude/settings.json` fires them on SessionStart/Stop/etc.); otherwise noisy non-fatal timeouts. | set-core: ensure provisioned worktree agents inherit the set-core bin PATH. | set-core |

### What already works — do NOT "fix"

- **The entire e2e path is worktree-exemplary:** `scripts/e2e.ts` requests a free port (`listen :0`), forces `PW_FRESH_SERVER=1`, resolves to the disposable `…_e2e`; `playwright.config.ts` sets the `_e2e` `DATABASE_URL` before the webServer spawns and injects `AUTH_URL`/`AUTH_TRUST_HOST` for dynamic ports; `ensure-build.ts` roots off `__dirname` and keys the `.next` cache on `HEAD + working-tree hash`, so each worktree builds independently. None need changes.
- **`db:reset` and e2e cannot touch the live copy** — `assertDisposable` refuses any non-`_dev`/`_e2e` or non-local target. The gap is only the **raw-`DATABASE_URL` consumers** (#1), not the resolver-mediated ones.
- **`prisma generate`** is covered by `postinstall`; the client is regenerated per-worktree. **`.husky/_`** regenerates via `prepare: husky` on install (also what re-arms #2/#3).

**Top three to action:** #1 (keep prisma pre-build off the raw production mirror; repoint `env_vars` to `_dev`/`_e2e`), #2 (`--no-verify` on automated worktree commits), #4 (`playwright install` in pre-build).

---

## 4. List C — Author-adds-first interface files

The minimal set of declarations so set-core **discovers** the consumer's automation rather than reimplementing it. Everything below already exists in the repo as a script — these files just point at it. Items 1–3 help today; 4–5 pair with the framework reader (List A / final-plan Phase 4).

| # | File | Declares | Removes which re-implementation / discovery failure |
|---|---|---|---|
| 1 | **`set/contract.yaml`** (new — the declaration surface; does not exist yet) | `lifecycle:` map pointing each op at the existing script: `install: pnpm install`, `schema_sync: pnpm db:reset`, `db_reset: pnpm db:reset`, `db_seed: pnpm db:seed`, `build: pnpm build`, `test: pnpm test`, `e2e: pnpm run test:smoke`, `release_e2e: pnpm run test:release-e2e`, `lint: pnpm lint`. Plus `e2e: { result_file: .e2e/last-run.json, result_schema: {ok,total,passed,failed,flaky,skipped,failures[]}, reset_on_start: true, teardown: false }`. ~25 lines. | The abstract interface itself. Until it exists there is nothing to delegate *to*, so every op silently falls back to set-core's own implementation — **including the destructive one**. Single source of truth that lets set-core call three-DB-safe `db-local.ts` instead of raw prisma, read the structured result instead of scraping stdout, run the intended e2e scope, run the real eslint. |
| 2 | **`set/orchestration/config.yaml`** (edit) | `e2e_command: pnpm run test:smoke` (pin the gate to `@smoke`, keep `e2e_timeout: 3600`). Optionally `smoke_command` for the release gate. | Stops set-core auto-selecting the heavy full `test:e2e` suite as the per-change gate; makes e2e scope an explicit decision, not a candidate-list accident. |
| 3 | **`CLAUDE.md`** (edit, consumer root) — new "Database model" section | Three-DB model: base name = untouchable live-data copy; `+_dev`/`+_e2e` disposable; `assertDisposable()` refuses destructive ops elsewhere; e2e is reset-on-start, no teardown; reset/seed go through `pnpm db:reset`/`db:seed`, never raw prisma. | Base knowledge every worktree agent (and set-core's own pre-build once it delegates) needs so nobody hand-rolls `prisma db push`/`migrate` against `DATABASE_URL`. |
| 4 | **`.claude/rules/db-never-raw-prisma.md`** (new rule) | Hard rule: NEVER run `prisma migrate`/`db push`/`db reset` against `DATABASE_URL` directly; destructive DB ops go through `pnpm db:reset`/`db:seed`, which target `_dev`/`_e2e` and enforce `assertDisposable`. | Protects both worktree agents and set-core-driven runs from the live-DB-wipe path. |
| 5 | **`scripts/gates/gates.yaml`** (new manifest) | Enumerate the 16 gate scripts, each with `path`, `phase` (pre-merge/post-merge/advisory), `blocking: true\|false`, `interpreter`. Baselines for the ratchet gates stay consumer-owned. | Turns 16 invisible hand-authored gates into a discoverable list. Without it set-core re-derives migration/testid/regression checks it partly owns — or skips them. (Needs the framework gate-runner to consume it.) |

**Not needed:** no new agents or skills. The reset-on-start convention belongs in CLAUDE.md (#3) + the contract (#1), not a bespoke agent. `set/knowledge/project-knowledge.yaml` already exists and is the natural sibling if the author prefers to fold the contract there rather than a new file.

**The one thing to land on both sides together:** the consumer's harness forces `--reporter json`, so set-core's list-reporter regex scraper reads **every green run as 0/0 and misdiagnoses it as a crash**. Author mitigation (`contract e2e.result_file`, item 1) and framework mitigation (read it, final-plan Phase 0b/4) must ship in the same step, or the very first delegated e2e gate reports a false failure.

---

## 5. Sequencing

**Author does first (consumer side, no framework dependency):**
1. Repoint `config.yaml env_vars` → `…_dev` + explicit `E2E_DATABASE_URL: …_e2e` (Blocker #1 defense-in-depth). This is the single highest-safety consumer action.
2. Write `CLAUDE.md` three-DB section (C-3) + `db-never-raw-prisma.md` rule (C-4).
3. Add the missing per-worktree provisioning: idempotent DB `provision`/teardown target (A-1), `mkdir -p` for the required dirs (Blocker #8), relativize the `domain-brief-hook` path (#5), honor `PORT` in `dev` (#7), move real prod tokens out of the copied `.env` (#9).
4. Write `set/contract.yaml` (C-1) and `scripts/gates/gates.yaml` (C-5) pointing at existing scripts, and add a normalized vitest result file (A-2). These are inert until set-core learns to read them, but authoring them now is cheap and unblocks the framework work.

**Where it meets final-plan:** Blocker #1 (set-core primary) **is** final-plan **Phase 0** — the data-loss guard at `project_type.py:2015` that stops `integration_pre_build` running raw prisma against the copied URL. The contract reader, db-lifecycle first-class ops, `e2e.result_file` reader, and gate-script runner are **Phase 4** (checks-as-gates) plus the delegation-contract `set-result/v1` schema (`delegation-contract-2026-07-14.md §3.2-3.3`). Treat this document's List A/C as the consumer-side inputs those phases consume. Blockers #2 and #3 (`--no-verify` on automated commits/pushes) are small, self-contained set-core changes that gate any worktree run and should land as a **Phase 0a** alongside the data-loss guard — they are independent of the contract reader.

**Is the project ready today?** **No — not for an unattended run.** Two of the three hard blockers are live: `DATABASE_URL` resolves to the production mirror and set-core's pre-build authors destructive prisma against it (Blocker #1), and automated worktree commits will be aborted by re-armed lefthook pre-commit hooks (Blocker #2). Either one alone is disqualifying — the first risks the live-data copy, the second stalls the run in a retry storm. **The minimum bar for a first, supervised worktree run is:** (Phase 0) set-core's pre-build no longer touches the raw copied `DATABASE_URL`, (Phase 0a) automated commits/pushes run `--no-verify`, and (consumer) `env_vars` repointed to `_dev`/`_e2e` with the disposable-DB provision target in place and Playwright browsers installed in pre-build. Contract-driven delegation (Lists A/C) is what makes runs *safe and repeatable* rather than *supervised and lucky* — but it is the second milestone, not the gate for the very first run.

---

## 6. In one line

set-core owning concrete decisions it can't safely make — which DB is disposable, whether a green e2e run passed — is what produced the data-loss path and the false-green; the fix on both sides is the same move: the consumer declares its existing three-DB / result-file / gate-script automation through `set/contract.yaml`, set-core delegates to it, and the trunk-based repo gets worktree-hardened (hooks off on automated commits, `DATABASE_URL` off the live copy, per-worktree provisioning) before the first run.
