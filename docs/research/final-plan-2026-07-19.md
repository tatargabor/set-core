# Sequenced Safety & Delegation Plan for set-core

**Thesis:** The consumer has already built the entire safety apparatus set-core needs to delegate to — so the fix is not to invent capability, it is to stop set-core from authoring one destructive command around it, then wire set-core to read what the consumer already produces.

**Date:** 2026-07-19
**Method:** Every call site read (not grep-only); classifications verified against both set-core source and the live consumer tree; Phase 0 adversarially refuted twice and corrected. file:line refs are into set-core unless a path is named.
**Supersedes:** the three 2026-07-14 research docs (worktree-removal study, orchestration post-mortem, delegation-contract note). Where they disagree with this document, this document wins — it folds in consumer ground truth those docs predate.

> Consumer project name, person names, and vendor names are omitted per `CLAUDE.md`. Disposable DB names are shown generically (`app`, `app_dev`, `app_e2e`). All set-core evidence is file:line in this repo; consumer evidence is generic relative script paths reproducible from any consumer's tree.

---

## 0. Status — updated 2026-07-19, end of day

**Phase 0′ is SHIPPED** (`8fae5733`). The guard sits in `integration_pre_build` between `prisma generate` (kept — it emits client code, touches no rows, and the build gate needs it) and the `db push` (now skipped unless the target is `file:`). It is a **skip, not a substitution**: `migrate deploy` applies the branch's pending migrations to whatever `DATABASE_URL` names. 8 tests in `tests/unit/test_integration_pre_build_db_guard.py`, **mutation-checked** — reverting the guard fails exactly the 4 blocking cases and leaves the 4 must-not-over-block cases green. Related suite unchanged: 487 passed before and after.

**DECISION: no `set-project init` against the live consumer project until Phase 0a ships.** Today an `init --force` would clobber the consumer's i18n catalogs (554→57 lines), its reset-on-start `tests/e2e/global-setup.ts`, and 16 hand-authored rules — see §4. The framework needs further work first; this is a **gated hold, not an open-ended one.**

**The gate that reopens it — all four, then re-evaluate:**

| | Item | Status |
|---|---|---|
| 0′ | DB-mutation guard on `integration_pre_build` | **done** (`8fae5733`) |
| 0′b | The twin: `e2e_pre_gate`'s guard reads the `.env` FILE while the push uses the `env` PARAMETER, and never fires when `DATABASE_URL` is absent | open, ~4 lines + test |
| 0a | Manifest `protected:true` flags — **the item that unblocks a safe re-init** | open, ~1 day |
| 0a′ | `--no-verify` on automated worktree commits/pushes (else re-armed hooks stall the run) | open, small |
| 0b | e2e gate reads a machine-readable result file keyed on `(file, title)` | open, ~1–2 days |

**Known unrelated debt, untouched:** 17 failed / 21 errors in `test_web_api_write.py` + `test_web_integration.py` (`AttributeError` in web API fixtures). Pre-existing — identical before and after Phase 0′.

**Discipline note.** Between 2026-07-14 and Phase 0′, this repo produced five research documents and zero lines of code while a six-line guard stood between an orchestration run and a production-data mirror. See `set-factory-verdict-2026-07-19.md` §4(5). Research is not the default next step here; shipping the listed items is.

---

## 1. What changed since 2026-07-14

Since the 2026-07-14 docs, the consumer project built out extensive custom safety infrastructure. That single fact both **validates** the delegation-contract direction and **exposes** a live data-loss path the earlier docs did not see.

**What the consumer built (verified 2026-07-19):**

| Artifact | What it is | File (consumer tree) |
|---|---|---|
| Three-DB model | `app` prod-copy = UNTOUCHABLE live data; `app_dev`, `app_e2e` = disposable | `scripts/lib/db-target.ts` |
| `assertDisposable()` | Throws unless target DB name ends `_dev`/`_e2e` AND host is local | `db-target.ts:86-115` |
| Suffix resolver | Appends `_dev`/`_e2e` to the base DB name, idempotent; no CLI target arg | `db-target.ts:53-76` |
| Reset-on-start e2e | `global-setup` force-resets `_e2e` before the run; **NO teardown** on crash — SIGKILL-safe | `scripts/e2e.ts` |
| Normalized e2e result | `.e2e/last-run.json` `{ok,total,passed,failed,flaky,skipped,failures[{file,title,message}]}` — **line-free** | `scripts/e2e.ts:32-66,187-194` |
| PreToolUse firewall | Blocks `prisma migrate reset`, force-push to main, prod deploy from the machine | `scripts/hooks/bash-damage-control.py` |
| 16 hand-authored gate scripts | check-migration, check-bug-regression-tests, check-e2e-testids, check-adversarial-review, … | `scripts/gates/` |
| ~57 custom rules, 5 agents, 5 workflows, 6 hooks | non-prefixed, project-specific | `.claude/` |

**What it PROVES (adoption evidence).** A delegation contract is not a speculative extension point. Mapping a hypothetical `contract.yaml` onto the consumer: **14 of 15 surfaces already have a live artifact (~93%); 11/15 are contract-ready as-is (~73%).** The one empty surface — `isolation.teardown` — is empty *on purpose* (replaced by reset-on-start). This is the exact opposite of a dead flag like `run_on_integration` (defined once, set in 5 places, **zero readers, zero demand**). The contract would describe behavior a live producer is begging set-core to read.

**What it EXPOSES (the guard-bypass data-loss path).** The consumer's guards assume a **human** threat model — they block a human running `prisma migrate reset`, or a human force-pushing. They do **not** anticipate set-core *authoring its own prisma command against `DATABASE_URL`*. And that is exactly what set-core does:

- `project_type.py:2015` runs `npx prisma db push --skip-generate --accept-data-loss` with `PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION=true` (:1995), in `integration_pre_build()`, called on **every merge gate pipeline** (`merger.py:1763`), `cwd=wt_path`.
- The worktree `.env` is a **verbatim copy** of the consumer `.env` (`dispatcher.py:759`, `:1073-1078`), so `DATABASE_URL` = the prod-copy DB. The PORT append (`dispatcher.py:1113`) is append-only and cannot rewrite it.
- This **bypasses `assertDisposable`** (set-core never calls `db:reset`, it writes its own command) **and slips past the firewall** (`db push` is explicitly on the allow-list, `bash-damage-control.py:159-160`).
- The twin at `project_type.py:2066` (in `e2e_pre_gate`) is **guarded** by `:2058` (`if not db_url.startswith("file:"): return True`). That guard was written and **never copied to :2015**.

The prod-copy DB is genuinely exposed on the next orchestration run. This is the single item that cannot wait.

---

## 2. Phase 0 — the ship-today fix (corrected)

The revised plan proposed substituting `prisma migrate deploy` for the destructive `db push`. **Adversarial review refuted that**, and the refutation holds: `migrate deploy` is **not inert against the prod copy**. It applies every pending migration in the branch to whatever `DATABASE_URL` names — and in a worktree that is the live-data copy. In-flight branches carry schema changes whose migration files routinely include `DROP COLUMN`, `ALTER COLUMN TYPE`, `DROP TABLE`, `SET NOT NULL` on populated rows. It also writes `_prisma_migrations` even in the benign case, and against a data-bearing DB with drifted history it hard-fails **P3005/P3009 on essentially every run** — halting orchestration for all changes. "Non-destructive" is not "inert" on a live DB.

The consumer's `migrate deploy` is safe **only** because `db:reset` routes it through `assertDisposable` + the suffix resolver — never `DATABASE_URL` directly. set-core bypasses that resolver, so copying the *command* reintroduces the exact bypass. Migrate-deploy only becomes safe once Phase 2 supplies a disposable target.

**Therefore Phase 0 is: guard and SKIP. Author no DB-mutating command against a non-`file:` target. Mirror the proven-safe twin at :2058 exactly.**

**Exact change** — `modules/web/set_project_web/project_type.py`, immediately before the `db push` at :2015 (so it reads `env["DATABASE_URL"]` *after* the drift-recovery block at :1985 may have repointed it):

```python
# Mirror e2e_pre_gate:2058. set-core must NOT author ANY DB-mutating command
# (db push OR migrate deploy) against a shared/live target. migrate deploy is
# not read-only — it applies branch migrations to whatever DATABASE_URL names,
# which in a worktree is the copied prod URL. Only SQLite (file:) worktrees,
# which are per-worktree-disposable, get a schema sync. Postgres/MySQL targets
# are provisioned out-of-band (Phase 2 isolation); here we do nothing.
db_url = env.get("DATABASE_URL", "")
if not db_url or not db_url.startswith("file:"):
    logger.warning(
        "integration_pre_build skip_db_sync wt=%s reason=non_sqlite_or_missing_target "
        "db_url_prefix=%s — refusing prisma db push/migrate against a shared DB",
        wt_path, db_url.split(":", 1)[0] if ":" in db_url else (db_url[:8] or "<empty>"),
    )
    return True
```

**Rules of the patch:**
- Keep `prisma generate` (:2000) — it emits client code, never touches rows.
- Leave the guarded `db push` in place for the `file:` branch (per-worktree-disposable SQLite).
- **Do NOT** chain `prisma db seed` on the non-`file:` path — seed mutates rows; the twin's seed at :2079 is only safe because the whole function early-returns first.
- Guarding on **empty** `db_url` too (`not db_url or …`) is slightly stronger than the twin and free — an empty URL would only make `db push` fail anyway.
- **Defer** asserting the resolved target is disposable: "disposable" is defined by the consumer's `db-target.ts` (`_dev`/`_e2e` + local-host), invisible to set-core. Encoding it is Phase 1 (contract) work. The skip-everything guard makes it moot — we author nothing against the shared target, so there is nothing whose target needs asserting.

**What this trades:** schema-additive branches lose build-time schema sync against the prod copy and may false-block at build/e2e. That is (a) **identical to today's e2e-path behavior** (the guarded twin already skips), and (b) a recoverable false-block versus irreversible prod mutation. Correct trade for a ship-today hotfix. All Postgres/MySQL schema-sync is delegated to the consumer's own reset-on-start until Phase 2 supplies a disposable target.

**Scope check (from the destructive-ops sweep):** the `:2015` push is the **only** unguarded data-loss site that reaches the live DB. The twin at `:2066`/`:2079` is guarded; the self-heal `.env` rewrite at `gates.py:535` is worktree-scoped and inert for this consumer (no `env_vars.DATABASE_URL` in config → `_resolve_database_url_from_config` returns None); the bootstrap `.env` write at `project_type.py:1325` never fires (`.env` always exists post-copy). No other data-loss site needs guarding in Phase 0. Two refinements from the sweep: the migrate/seed path must never chain `prisma db seed`, and because env-drift recovery at `:1985` can repoint `DATABASE_URL` from `config.yaml`, any future non-disposable `env_vars.DATABASE_URL` must not silently become a mutation target — the skip guard already covers this since it refuses all non-`file:` targets.

---

## 3. Revised, dependency-correct phase sequence

The three genuinely safety-critical items are **all small, standalone, shippable this week** — the revised plan buried two inside multi-week architectural phases. Split them out. "Phases 0+1+2 deliver all safety value" is **false**: two first-order safety issues (e2e false-green, deploy clobber) live *outside* 0/1/2 and are not architectural.

### Ship now — standalone fixes, no second consumer needed

| Phase | What | Change | Est. |
|---|---|---|---|
| **0′** | Data-loss guard | Literal SKIP guard at `project_type.py:2015` (§2). NOT migrate-deploy. | ~6 lines, today |
| **0a** | Deploy protected-flags | In the web `manifest.yaml`: flag `messages/*`, `tests/e2e/global-setup.ts`, `.gitignore`, `.husky/pre-commit`, `src/lib/*`, `project-knowledge.yaml` as `protected:true`; set-prefix-or-protect the 23 `rules/` entries; fix the `code-reviewer.md` basename collision. One line per entry. **Unblocks safe re-init** — and protects the reset-on-start `global-setup.ts` that Phase 2 depends on. | ~1 day |
| **0b** | Bug 2 adapter | e2e gate reads `.e2e/last-run.json`, keys failures on `(file,title)` (already line-free). Fixes the false-green where the gate scrapes the Playwright *list* reporter (`gates.py:861`) and reads zero failures from the consumer's JSON reporter. | ~1-2 days |

0a is the **highest-leverage safety change after Phase 0** and is fully independent of the contract work. 0b's exact urgency depends on one unverified fact (§5): if the e2e gate also hard-fails on `scripts/e2e.ts` exit code, Bug 2 only breaks the pre-existing-failure *allowance*; if not, it is a **full false-green** shipping broken code silently.

### Architectural — each gated by a second-consumer E2E run

| Phase | What | Depends on | Est. | Note |
|---|---|---|---|---|
| **1** | `lib/set_orch/contract.py` + `set/contract.yaml` (optional, never templated). Resolution: contract > directives > `profile.detect_*` > None. **None ⇒ gate skips AND LOGS why** (today it skips silently — that is how Bug 2 hid). | — | ~3 d | Enables 2. The "skip-logs-why" sub-item is a trivial logging fix — ship it early. |
| **2** | Isolation. Rewrite worktree `.env` `DATABASE_URL` to the disposable `_e2e` DB (feed the consumer's suffix resolver), replacing the append-only guard at `dispatcher.py:1113`. Disposable-URL value must come from a profile/contract hook — `dispatcher.py` is Layer 1, cannot hardcode `_e2e` (modular rule 1). After this, 0′'s conservative skip can re-enable `db push` against the per-worktree disposable DB. | 1 | ~4 d | **Correction:** consumer `.env` has only `DATABASE_URL`; `DEV_/E2E_DATABASE_URL` live in `.env.example`. Isolation runs through the suffix resolver, not explicit env vars. **Under `max_parallel=1` (E2E default, on purpose), per-worktree distinct DB naming is unnecessary** — the single worktree uses shared `app_e2e` + reset-on-start. Don't build per-worktree naming now. |
| **3** | `set-result/v1` schema + adapter reading `.e2e/last-run.json`. Add schema version to baseline cache key (`gates.py:1030`). Keep `test_coverage.py` stub detection. | 0b done | ~1 wk | Bug 2 already fixed in 0b — this is the durable schema, not the hotfix. Genuine adoption risk is `results.test` (vitest emits exit-code only, no normalized JSON) and `results.policy` (implicit in exit codes + config). Scrutinize here that the contract ships no field no artifact populates. |
| **4** | Checks-as-gates: synthesize a `GateDefinition` per contract `checks[]` entry (maps the 16 consumer gate scripts). Wire `run_on_integration` HERE. | **1, NOT 3** | ~4 d | Consumer gate scripts are exit-code pass/fail — they don't consume `set-result/v1`, so this needs only Phase 1's `checks[]` and runs **parallel to** Phase 3. Wiring `run_on_integration` turns a dead flag live — the 5 gates currently set-True start running on the merge path and can newly-block merges. Needs second-consumer validation. |
| **5b** | sha256 `set/.deploy-manifest.json` per file + tombstones for deleted set-* rules (bucket E: stateless deploy resurrects deleted files). | 0a shipped | ~3 d | The *narrowed* "set-* files only" scope is **wrong** and demolished by the deploy audit — the biggest clobbers (16 rules, i18n, global-setup) are NOT set-*-prefixed; 0a handles those now. 5b is only the residual resurrect-deleted problem. |
| **6** | Move e2e + lint from `modules/web/` to universal `set`, parameterized by `lifecycle_command()`. | 3 | ~4 d | Pure refactor, **zero safety value**, correctly last. `gates.py`/`_extract_e2e_failure_ids` are already Layer 2 — "make universal" = move-or-adapter, not new code. Needs full web E2E suite + second consumer (Playwright JSON quirks, failure-ID extraction must survive identically). Droppable from the safety track. |

**Corrected claim:** *Phase 0′ + 0a + 0b* deliver essentially all safety value, and none is architectural. Phases 1-2 are hardening/enablers; 3-6 are durability and reach.

**Timeline:** raw sum ≈ 23 working days, but that omits second-consumer validation cycles (2/4/6 each need an orchestration E2E run) and true Phase 5 is 2-3× the narrowed estimate. Realistic **~6-7 weeks to the full arc** — but the safety-critical trio is **this week**.

---

## 4. Re-deploy preserves vs clobbers — the author's fear, answered

`set-project init` on an already-registered project re-runs with `--force` (`bin/set-project:717-721`). Two engines: `deploy_set_tools` (bash, never force-gated) and `_deploy_project_templates` (force, via `profile_deploy.py`). Under `--force` each manifest entry resolves to: `merge:true` → additive; `protected:true` + differs → **skip**; **neither flag → unconditional `shutil.copy2` overwrite**. The web manifest leaves most files unflagged. Verified against the live consumer:

| Path | Fate today | Consumer impact |
|---|---|---|
| `commands/set/*`, `commands/opsx/*`, `skills/set/*`, `skills/openspec-*/*` | **Preserved** (namespaced `cp -r`) | none |
| `set/orchestration/config.yaml` | **Preserved** (additive merge) | `e2e_timeout:3600`, `max_replan_cycles:3`, `test_command:pnpm test` all kept — existing keys never overwritten |
| `set/plugins/project-type.yaml` | **Preserved** (managed-field merge) | only `type/version/description/template/modules` rewritten; commented override surfaces kept |
| `package.json`, `vitest/playwright/tsconfig/next.config`, `globals.css`, `.env.example`, `eslint.config.mjs` | **Preserved** (`protected:true`, differ → skip) | none |
| `CLAUDE.md` | **Preserved** (marker-guarded append) | none |
| `settings.json` (hooks) | **Preserved** (jq-surgical, backup, touches only `set-hook-*`) | firewall PreToolUse entry survives. **Latent**: the fresh-merge branch would replace whole event arrays if settings leave "canonical" |
| **`messages/hu.json` + `messages/en.json`** | **CLOBBERED** (core, no flags) | 554→57-line stub — **total i18n content loss**. Most severe. |
| **`tests/e2e/global-setup.ts`** | **CLOBBERED** | 216→264L — **destroys the reset-on-start SIGKILL-safe harness Phase 2 depends on**. Cross-phase inversion. |
| **16 rules** (`auth-conventions`, `nextjs-patterns`, `schema-integrity`, `deployment`, `e2e-test-layering`, `error-handling`, `functional-conventions`, `integrations`, `performance`, `playwright-assertions`, `seed-conventions`, `testing-conventions`, `ui-conventions`, `web-conventions`, `web-frontend`, `worktree-setup`) | **CLOBBERED** | deploy to `.claude/rules/<name>.md` with **NO set- prefix** (`_SET_PREFIX_PATHS` = `framework-rules/` only, `profile_deploy.py:35`) → collide by bare name, silently overwritten by web-generic versions |
| **`.claude/agents/code-reviewer.md`** | **CLOBBERED** (basename `cp`, un-namespaced) | consumer's custom agent overwritten |
| **`.gitignore`** | **CLOBBERED** | 102→51L (template still ignores `.env`, so no credential exposure, but custom ignores lost) |
| **`.husky/pre-commit`**, **`src/lib/auth/storage-state.ts`**, **`project-knowledge.yaml`** | **CLOBBERED** | consumer versions overwritten |
| `.claude/rules/set-*.md` (9 core + 7 framework) | **CLOBBERED only if hand-edited** | namespaced, no collision with the 57 custom rules; edited → clobber, deleted → resurrect |
| ~57 non-prefixed custom rules (other than the 16), 5 agents (other than `code-reviewer`), 5 workflows, 6 hooks, 16 gate scripts | **Preserved** | `cp` never deletes; not in manifest |
| Any **deleted** framework file (rule, agent, skill, command) | **RESURRECTED** | stateless deploy: `if dst.exists(): overwrite else: deploy` — no tombstone anywhere |

**Direct answer to the fear:** re-deploy today preserves config, namespaced commands/skills, and every non-prefixed custom rule *except the 16 that collide by bare name* — but it **clobbers i18n, the reset-on-start harness, 16 rules, the custom code-reviewer, .gitignore, husky, auth-state, and project-knowledge**, and **resurrects any deliberately-deleted framework file**. **Phase 0a closes the clobbers today (one line per manifest entry); Phase 5b closes the resurrections later.** The narrowed "set-* only" Phase 5 would have left every one of the un-prefixed clobbers live — including the very `global-setup.ts` a later phase builds on.

---

## 5. Resolved n=1 unknowns vs still-open

**Resolved by reading the consumer tree:**

| Unknown | Resolution |
|---|---|
| Test-id / failure-id **line stability** | Resolved. The consumer's `.e2e/last-run.json` failures are **`{file,title,message}` — line-free** (`scripts/e2e.ts:187-194`). Keying on `(file,title)` works today; set-core's brittle `file:LINE` regex against the *list* reporter (`gates.py:861`) is the wrong surface. |
| **Teardown / SIGKILL** safety | Resolved. Consumer has **NO teardown by design** — `global-setup` **force-resets `_e2e` on start** (RESET-ON-START), so a SIGKILL'd run leaves no poisoned state; the next run resets. The contract must *accommodate* an absent teardown, not offer a teardown hook. |
| `db:reset` **env resolution** | Resolved. `db:reset` resolves target via the **suffix resolver** (`db-target.ts:53-76`: base name + `_dev`/`_e2e`, idempotent) gated by `assertDisposable`; **no CLI target arg**. Phase 2's env-overlay must feed *this resolver* (rewrite `DATABASE_URL` so its suffixed target is disposable), not invent explicit `DEV_/E2E_DATABASE_URL` vars in `.env`. |
| Is the delegation contract a **7th dead extension point**? | Resolved: **no**. 14/15 surfaces have a live consumer artifact; the contract would describe running behavior. `run_on_integration` is the dead flag; the contract is its opposite. |

**Still open:**

| Open unknown | Why it matters | How to close |
|---|---|---|
| Does the e2e gate **hard-fail on `scripts/e2e.ts` exit code** (1 = test-fail)? | Decides whether Bug 2 is a **partial** false-green (only the pre-existing-failure *allowance* breaks — NEW failures waved through as "pre-existing") or a **full** false-green (broken code merges silently). Sets 0b's urgency: "this week" vs "today". | Read the e2e gate's exit-code handling around `gates.py:1351` / `:1546`; run one consumer e2e gate with a known-failing test and observe merge outcome. |
| `results.test` / `results.policy` adoption | vitest emits **exit-code only, no normalized JSON**; policy is **implicit** in exit codes + config, not declarative. These are the only two surfaces with no consumer artifact to read. | Phase 3 scrutiny: either add a vitest-JSON-reporter adapter or don't ship the declarative fields. |
| Second-consumer validation for Phases 2/4/6 | n=1 today. Isolation env-rewrite, `run_on_integration` going live, and the universal e2e/lint move all need a second project to avoid over-fitting to this consumer's suffix/reset-on-start conventions. | Gate each of 2/4/6 behind an orchestration E2E run on a second registered project. |

---

## 6. In one line

Ship the 6-line SKIP guard at `project_type.py:2015` and the one-line-per-entry `protected:true` manifest flags **today** — the consumer already built assertDisposable, reset-on-start, and a line-free result file, so everything after Phase 0 is set-core learning to delegate to safety infrastructure that already exists.
