# The Delegation Contract: Who Owns the Command, Who Owns the Verdict

**Date:** 2026-07-14
**Method:** 57-agent research workflow (assumption census → contract design → adversarial refutation)
**Question asked:** *"Do we need a new project type whose whole point is that we inject nothing — no rules, no seed,
no ORM files — and the consumer project implements those itself, with set-core's Python abstraction merely calling
them?"*
**Answer:** **No — and the framing is wrong.** Delegation is a **layer**, not a **type**. And it must carry **facts**,
not just exit codes.
**Companions:** [`orchestration-postmortem-2026-07-14.md`](orchestration-postmortem-2026-07-14.md) ·
[`worktree-removal-study-2026-07-14.md`](worktree-removal-study-2026-07-14.md)
**Status:** Phase 0 is a live data-loss bug — ship it before anything else here.

> Consumer project names are omitted per `CLAUDE.md`. All evidence is file:line in this repo or reproducible from
> any consumer's orchestration artifacts.
>
> **n=1 caveat.** Every conclusion below is drawn from **one** real consumer (Next.js / Prisma / Postgres /
> Playwright). Where that matters, it is flagged. **Do not freeze the contract schema until a structurally different
> project has been run against a draft.**

---

## 0. The two live bugs this study found

Both are in `main` today. Neither was known before.

### Bug 1 — a destructive schema push against the developer's own database

`modules/web/set_project_web/project_type.py:2015` runs, in `integration_pre_build()`:

```
npx prisma db push --skip-generate --accept-data-loss
```

…with `PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION=true` (`project_type.py:1995`). Its **only** precondition is that
`prisma/schema.prisma` exists (`:1928-1930`).

Its twin, `e2e_pre_gate()`, **does** guard — `project_type.py:2058-2059`:

```python
if not db_url.startswith("file:"):
    return True  # Not SQLite — skip for now
```

**The guard was written, and never copied to the destructive path.** Meanwhile `dispatcher.py:759` / `:1073-1078`
copies `.env` **verbatim** into every worktree, so every worktree inherits the same `DATABASE_URL` — which on the one
real consumer is `postgresql://…`, the database its own dev server reads. **`grep worktree_database` → zero hits
repo-wide.**

### Bug 2 — a silent, prospective disabling of the e2e baseline compare

The main-baseline compare works (`gates.py:1002`, `gates.py:1717`) — and it works **only because the project happens
to print Playwright's default *list* reporter**. `_extract_e2e_failure_ids` (`gates.py:861`) scrapes it with a regex:

```python
re.finditer(r"^\s*\d+\)\s+\[.*?\]\s+[›»]\s+([^\s:]+\.spec\.\w+:\d+)", clean, re.MULTILINE)
```

The consumer has since replaced `test:e2e` with its own harness, and that harness forces `--reporter json`
(`scripts/e2e.ts:138`). **The regex matches zero lines against JSON.** So `wt_failures == set()`, and `gates.py:1646`
returns **fail before the baseline compare ever runs** — telling the agent *"the suite crashed, check for OOM kills."*

**The consumer improving its own test harness silently disabled the framework's single best feature.** That is the
real indictment of the current design, and it is the argument for the whole contract: **as long as set-core's verdict
depends on scraping human-readable output, every consumer is one `--reporter` flag away from a lie.**

A third defect, related: **test identity is keyed on `file:LINE`.** The one real baseline run in June cached ids like
`…spec.ts:129`. **One inserted line in that spec manufactures two false regressions.**

---

## 1. Why a new project type is the wrong instrument

Three structural facts, each from the code:

1. **A type cannot stop the overwrite.** The core-rule deploy is **profile-blind**: `lib/project/deploy.sh:191` is an
   unconditional `cp "$src_file" "$dst_rules/set-$base_name"` inside a `find` loop, inside `_deploy_skills()`, which
   takes exactly one argument — a path (`deploy.sh:138-139`, called from `bin/set-project:214`). No profile, no hash
   check, no backup. **A `type: contract` clobbers hand-edited rules exactly as `type: web` does.**

2. **A type cannot reach half the assumptions**, because they live in **Layer 1**, where no profile has an override
   point: `verifier.py:2657` returns `GateResult("build","skipped")` when there is no `package.json` — and
   `_execute_build_gate` (`verifier.py:2650`) **does not even take a profile argument**. `merger.py:2911-2914`
   returns before `profile.post_merge_install()` unless `package.json` appears in the merge diff.
   `dispatcher.py:1113` appends the port to `.env` only `if "PORT=" not in existing` — **append-only**, so a copied
   `DATABASE_URL` can never be rewritten.

3. **The decisive one: `type:` is the wrong axis.** Five of the twelve gates live in `modules/web`
   (`project_type.py:1363-1456`: i18n_check, **e2e**, lint, design-fidelity, required-components), and **`CoreProfile`
   does not override `register_gates`** — it inherits `ProjectType.register_gates` → `[]` (`profile_types.py:734`).
   Switching a consumer from `type: web` to a scaffold-nothing `type: contract` would therefore **cost it the e2e gate,
   its baseline compare, and design-fidelity** — the only gates whose findings demonstrably bind into `retry_context` —
   in exchange for fixing prose rules and scaffold files.
   **The drift is on the *content* axis; the value is on the *mechanism* axis. `type:` conflates them.**
   And it **would not crash**: it boots, exits 0, prints a green health line, and runs an **empty pipe**. A loud failure
   stops you on day one; a silent one ships unverified code through a merge queue that believes it verified something.

### The right frame

> **set-core must stop being a *command author* and become a *verdict authority*.
> Delegation is a LAYER, not a TYPE — and the layer must carry FACTS, not exit codes.**

The literal proposal ("set-core merely calls them") is **half a design**. If set-core merely calls and reads an exit
code, it loses: baseline-compare, regression-vs-pre-existing attribution, flaky discrimination, harness-error-vs-test-
failure, retry scoping, and requirement→test coverage — i.e. **everything that is not `bash` + `git`.** That is the
empty pipe, arrived at by agreement rather than by accident.

**The contract is: the project owns the COMMAND and emits the FACTS; set-core computes the VERDICT and never trusts a
project-supplied one.**

---

## 2. Where the line is

### Category C — what set-core must keep knowing. Non-negotiable.

| # | Invariant set-core owns | Why a project-local script structurally cannot do it |
|---|---|---|
| **C1** | **The verdict** — pass/fail/skip for every gate | Depends on state the project cannot see: the main-branch baseline cached per `main_sha` (`gates.py:1002-1101`), other worktrees' failures, retry counters (`gate_runner.py:111`), the digest requirement set. **The consumer's own result file has an `ok` field. set-core must ignore it.** This is the anti-empty-pipe clause — write it into the spec verbatim. |
| **C2** | **When each gate runs** — order (`_resolve_gate_order`, `gate_runner.py:118`) and blocking mode per change type (`gate_profiles.py:130-175`) | The project supplies a string; it never gets to say where in the pipeline that string runs, or whether failing blocks. Otherwise *"gates cannot be talked past"* is a slogan. |
| **C3** | **The retry loop** — gate output → `retry_context` → the agent's next prompt (96 `retry_context` sites in Layer 1) | **The one mechanism no CI system has.** It is why gate findings get *fixed* rather than *reported*. It requires re-dispatching an agent into a live worktree. |
| **C4** | **Test identity = `(file, title)` — never a line number** | Load-bearing for C1/C5/C8. Today `gates.py:861` keys on `file:LINE`; **confirmed live**: one inserted line manufactures two false regressions. |
| **C5** | **`harness_error` vs `tests_failed`** | `GateResult.infra_fail` / `terminal_reason` already exist (`gate_runner.py:87-89`) and are currently **guessed from prose** (`gates.py:1652`). A harness error must not burn a retry or be charged to the agent. |
| **C6** | **Isolation is required for every mutable resource** | Enforced for ports (`dispatcher.py:1104-1118`), **not** for the database. The *requirement* is core's; the *mechanism* is the project's. |
| **C7** | **Serialized merge queue; no merge bypasses gates** | Cross-change. Cannot live in a repo script. |
| **C8** | **Requirement → test → assertion traceability, and anti-gaming** | `test_coverage.py:508`, `merger.py:2341`. **Stub detection cannot be deleted even with a perfect assertion count** — `expect(true).toBe(true)` *is* an assertion. The defence is `_count_meaningful_expects` (`test_coverage.py:209-231`), a **source-level** check no runtime counter replaces. |
| **C9** | **A change has a scope = a set of paths** | Needed for conflict prediction. The *concept* is core's; the *taxonomy* (`planner.py:645-672`, grouping by directory) is delegable and **must go** — see the post-mortem's invariant-shaped-slices finding. |
| **C10** | **Change state machine + dependency ordering** (`state.py`) | Cross-change. |
| **C11** | **The environment a command runs in** — gate env, secrets, timeouts, budgets | The project declares the string; **core decides what it inherits**, or C6 is unenforceable. |
| **C12** | **What is framework-owned vs consumer-owned on disk** | Today: nothing. See Phase 5. |

Everything else — *how* to install deps, *how* to reset a database, *how* to run e2e, *what* the rules say — belongs
to the project.

---

## 3. The contract

### 3.1 Where it lives — and the trap that killed a whole design

Put it in **Layer 1** (`lib/set_orch/contract.py`), **not on `CoreProfile`.**

**Reason:** `NullProfile` is a **sibling** of `CoreProfile` (`profile_loader.py:39` vs `:57`), and *every* fallback path
instantiates `NullProfile` (`profile_loader.py:234, 245, 255, 332`). Worse, `dispatcher.py:1092` gates all profile hooks
behind `if not isinstance(profile, NullProfile)`. **A contract implemented on `CoreProfile` would not reach the second
consumer** — a project on a stack with no module, which is the exact case the whole exercise exists to serve.

### 3.2 `set/contract.yaml` — new, optional, never templated, never overwritten

The consumer **keeps `type: web`** and keeps its five web gates.

```yaml
schema: set-contract/v1

lifecycle:                        # declared beats detected. "" = disabled. absent = fall back to profile.detect_*
  install:     "pnpm install --frozen-lockfile"
  schema_sync: "pnpm db:push"     # replaces integration_pre_build's hard-coded prisma push
  db_reset:    "pnpm db:reset"
  db_seed:     "pnpm db:seed"
  build:       "pnpm build"
  test:        "pnpm test"
  e2e:         "pnpm test:e2e"
  lint:        "pnpm lint"

isolation:                        # the missing dual of worktree_port(). REWRITE semantics, not append.
  env:
    PORT: "{port}"
    DATABASE_URL: "postgresql://localhost:5432/app_{slug}"
  provision: "pnpm db:provision"  # after env overlay, before any gate
  teardown:  "pnpm db:drop"       # idempotent; at e2e_post_gate / set-close

results:
  e2e:  { path: ".e2e/playwright.json", format: "playwright-json" }
  test: { path: "reports/junit.xml",    format: "junit" }
  policy: { required: true }      # false => degraded mode, loudly logged

checks:                           # the consumer's own gate scripts become first-class orchestration gates
  - id: migration-safety
    command: "bash scripts/gates/check-migration.sh"
    position: "after:test"
    severity: error
  - id: regression-tests
    command: "bash scripts/gates/check-bug-regression-tests.sh"
    position: "before:review"
    baseline: "data/bug-regression-baseline.txt"   # ratchet: may only shrink
```

### 3.3 `set-result/v1` — the crux

**An exit code cannot support C1, C4, C5 or C8.** This is the whole ballgame.

```json
{
  "schema": "set-result/v1",
  "kind": "e2e",
  "outcome": "passed | tests_failed | harness_error",
  "totals": {"passed":9,"failed":0,"flaky":0,"skipped":0,"total":9},
  "tests": [
    {"id": "tests/e2e/cart.spec.ts::Cart › adds item",
     "file": "tests/e2e/cart.spec.ts", "title": "Cart › adds item",
     "status": "passed|failed|flaky|skipped",
     "selector": "tests/e2e/cart.spec.ts:45",
     "assertions": 7,
     "message": "<=2KB first error"}
  ],
  "diagnostics": [{"severity":"error","file":"src/x.ts","line":12,"rule":"no-any","message":"..."}]
}
```

**Normative rules — these are what make a gate un-talk-past-able:**

- **R1** Core `unlink()`s the declared path **before** the run. A stale green file must never mask a crash.
- **R2** `totals` and `outcome` are **advisory**. Core recomputes the verdict from `tests[]`.
  `len(tests) != totals.total` ⇒ `harness_error`.
- **R3** A project-emitted `ok` field is **ignored**. *(The consumer's file has one.)*
- **R4** `outcome: harness_error` ⇒ `GateResult.infra_fail=True`, retry counter **not** incremented, gate re-runs.
- **R5** A **missing** `tests` key ⇒ `harness_error`. `tests: []` must be explicit.
  *"I forgot to emit the array"* must never read as *"the suite is green"*.
- **R6** Anti-gaming clamp: core cross-checks `len(tests)` against the spec files it counts on disk
  (`gates.py:899`). Deliberately scoped runs must be **declared** as scoped — see §6, open question 2.
- **R7** `id` **must not** contain a line number.
- **R8** `selector` is **opaque** to core, round-tripped verbatim for retry scoping.
- **R9** `assertions` is `null` when the runner cannot report it. **Verified:** Playwright's built-in JSON reporter
  emits **zero steps**, so `assertions` is unavailable via `playwright-json`. **Stub detection
  (`test_coverage.py:200-291`) therefore stays as the *primary* defence, not a fallback.**

**Adapters** in `lib/set_orch/results/` (`playwright_json.py`, `junit_xml.py`, `vitest_json.py`, `pytest_json.py`,
`go_test_json.py`) — pure bytes→`RunResult`, zero exec/fs surface, enforced by an import-firewall test.
**JUnit XML is the tier-2 fallback**: universal and line-free, but it has no flaky and no harness-error semantics —
which is exactly why it cannot be primary.

**Degradation ladder (normative):** result file → full gates. JUnit only → baseline works, flaky/assertions
unavailable. Neither → today's regex scraping, **and core MUST log the degradation and MUST NOT claim a baseline
comparison it did not perform.** Today it skips and says nothing (`gates.py:1700-1704`) — which is precisely how Bug 2
hides.

---

## 4. The four designs

Survival after adversarial refutation (code lens · empty-pipe lens · delivery-pressure lens):

| Design | Survival | Verdict |
|---|---|---|
| **4th built-in project type** (`modules/contract/`) — *the literal proposal* | **8%** | **Dead.** Cannot stop the overwrite (`deploy.sh:191` is profile-blind), cannot reach the Layer-1 hard-codes, and **costs the consumer 5 gates** including e2e + baseline. Fails **silently**, which is the worst possible failure mode for a merge queue. |
| **Consumer ships a Layer-3 plugin** (`entry_points`) | **35%** permanent · **90% as a 2-day stopgap** | ~60 lines, zero set-core changes, stops the destructive push **today**. But it hard-couples the consumer to the Prisma-shaped superclass it is trying to escape, and fixes nothing for consumer #2. **Right emergency valve, wrong permanent home.** |
| **Contract-as-layer** (`set/contract.yaml`) | **58%** | Survived. Two holes found: it was specified on `CoreProfile` (which the `NullProfile` fallback never reaches), and it delegated the *command* without fixing the *result* — so consumer #2 would get an exit code and nothing else. |
| **The result contract is the product** (`set-result/v1`) | **50%** | Its headline claim (*"baseline-compare never ran"*) was **empirically refuted** — it ran in June. But its architecture is right, and its **prospective** version is stronger: the baseline works only while the project prints the default reporter, and **breaks silently the moment the project owns its harness — which the consumer already did.** |

> **The last two are not rivals. The result contract is the missing half of the delegation contract.**
> **Contract without results** = the project owns every command and set-core reads exit codes = **the empty pipe**.
> **Results without contract** = set-core reads beautiful JSON and still force-pushes a schema at your dev database.

---

## 5. Sequenced remediation

**Constraint: must not break the live client project (12 corrective changes in flight), and must compose with the two
fixes already queued** (wire `run_on_integration`; per-change DB via `worktree_env_overrides`).

**PHASE 0 — DATA-LOSS HOTFIX. Today. ~6 lines. No dependencies. Lands before anything architectural.**
When `DATABASE_URL` is not `file:`, do **not** run `db push --accept-data-loss`. Run `prisma migrate deploy`
(non-destructive) and **fail the gate loudly on drift**. The guard already exists 40 lines away
(`project_type.py:2058`) — copy it. *Everything else in this document can wait; this cannot.*

**PHASE 1 — `lib/set_orch/contract.py` + Layer-1 call-site routing. ~3 days.**
Zero behaviour change when `set/contract.yaml` is absent. Single resolution point:
`contract > directives > profile.detect_* > None`. `None` ⇒ gate **skips and logs why** (today it skips silently).

**PHASE 2 — ISOLATION. ~4 days.** *(This is where the queued `worktree_env_overrides` work lands.)*
Replace the append-only `.env` guard (`dispatcher.py:1113`) with **line-rewrite** semantics. Split `e2e_gate_env`
(`profile_types.py:646`) — it currently conflates worktree **identity** (`PORT`) with gate **policy**
(`PW_FLAKY_FAILS`, `PRISMA_USER_CONSENT_…`) and writes all of it into the consumer's on-disk `.env`. Add `provision`
at bootstrap and `teardown` at `e2e_post_gate` / `set-close` — today `WebProjectType.e2e_post_gate`
(`project_type.py:2088-2092`) is a **literal empty no-op**, so any per-change DB would leak forever. Move
`worktree_port` off the range that collides with a typical dev server (`project_type.py:1883`).
**After this, Phase 0's conservative `migrate deploy` can safely go back to `db push` — because it now targets a
per-worktree database.**

**PHASE 3 — RESULT CONTRACT. ~1 week. Net deletion.**
Adapters ship dark. E2E gate dual-path: prefer `RunResult`, keep the regex as fallback.
**CRITICAL: add a schema version to the baseline cache key (`gates.py:1030`)**, or `file:LINE` baselines will be
diffed against line-free worktree ids and **every failure will read as new**. Re-key ids `file:LINE` → `file::title`
(`gates.py:861`) — this alone kills the confirmed false-regression bug. **Keep `test_coverage.py:200-291`.**

**PHASE 4 — CHECKS-AS-GATES. ~4 days.** *(Where the framework gets its teeth back — and where `run_on_integration`
gets wired.)* Synthesize a `GateDefinition` per `checks[]` entry; stdout/`diagnostics[]` → `retry_context`;
`baseline:` → a ratchet that may only shrink. **Wire `run_on_integration` here, *after* Phase 3** — wiring it before
would double the parser surface you are about to delete.
Also: the **rules gate is a live landmine.** All 15 rules default to `trigger="*"` (`verifier.py:1864`), 4 are
`severity=error`, and it **fails unconditionally** on a real consumer — survivable today only because it is `warn` in
5 of 6 change profiles and `skip` in the 6th. But the fallback map (`gate_profiles.py:150`) says `"rules": "run"`.
**Any profile that promotes it hard-fails every merge.** Fix or delete it.

**PHASE 5 — DEPLOY OWNERSHIP. ~3 days.**
`set/.deploy-manifest.json` with a sha256 per deployed file: hash matches → overwrite; hash differs → **skip and
report "consumer-owned"**. **Invert the default: protected unless `managed: true`** (today **0 of 23** template rules
carry `protected: true`). Add **tombstones** — human-deleted rules are currently resurrected by the `--force` that
re-init always passes (`bin/set-project:717-722`). Extend the `set-` filename prefix to `rules/` so framework rules
**can never collide** with consumer-authored ones — the same namespace discipline that already makes
`.claude/skills/set` and `.claude/commands/set` **completely conflict-free (0 of 30 differ)**.

**PHASE 6 — GATE MIGRATION. ~4 days + one full E2E.**
Move **e2e** and **lint** from `modules/web` down to the universal set (`verifier.py:3968-4007`), parameterized by
`lifecycle_command()`. Web keeps the genuinely Next-specific three (i18n, design-fidelity, required-components).
**After this, a Python service with no module gets build + test + e2e + lint + its own checks — the hole the 4th
project type was reaching for, closed without a 4th project type.**

**Total ~4–5 weeks. Phases 0+1+2 (≈1.5 weeks) deliver essentially all the safety value.**

**NON-STEPS:** do not create `modules/contract/`. Do not switch any consumer off `type: web`. Do not delete
`get_templates()` from the ABC in the same quarter as any of this.

---

## 6. What the consumer does

It **keeps `type: web`**. It **never forks a project type**. It plugs in through four surfaces:

1. **Write `set/contract.yaml`** (~25 lines), pointing `lifecycle:` at the scripts **it already declares** in
   `package.json`. set-core stops re-implementing them, badly, by hand.
2. **Declare `isolation:`.** Its DB-reset script must accept a **target database argument** rather than hard-coding
   one, and teardown must be idempotent under `SIGKILL` (worktrees get killed by the iteration timeout routinely).
3. **Emit a result file.** It already writes one and already exits **2** on harness error — a signal set-core has a
   *field* for (`gate_runner.py:87`) and currently **guesses**. Point `results.e2e.path` at the raw runner JSON (the
   adapter handles it, zero work), or emit `set-result/v1` directly. **Its `ok` field will be ignored — deliberately.
   That is the integrity guarantee, not an insult.**
4. **Register its gate scripts under `checks:`.** They stop being invisible to orchestration and start feeding
   `retry_context` — the one thing that makes an agent actually *fix* a finding rather than log it.

Then **its rules and skills evolve freely, forever, and set-core never touches them again** (Phase 5).

**Flow upstream** (failure classes generalize; domain facts do not): its production-regression rule **plus its gate
plus its ratchet baseline** is the highest-value candidate — a complete, working, measured instance of the exact
executable-rule contract proposed here. Also its adversarial-spec-review, derived-state and UI-entrypoint-integrity
rules. Its **rules self-report** tooling (gate-vs-prose ratio, dead-gate references, stale paths, context load) is
**framework-generic and set-core should own it** — the consumer's own retrospective is the argument:
*"the system knew nothing about itself — that is why a third of the corpus could stay false for months."*

---

## 7. What we still do not know

| # | Unknown | Cheapest experiment |
|---|---|---|
| 1 | **Is the runner's test `id` stable across line moves?** If it is derived from the line number, C4/R7 is dead and the baseline rewrite buys nothing. | Move a test down 10 lines, re-run, diff the `id` in the JSON. **5 minutes.** Do this **before** Phase 3. |
| 2 | **Does the anti-gaming clamp (R6) false-block a legitimately scoped run?** A `--grep @smoke` run deliberately executes 3 of 40 tests. If R6 cannot tell "scoped" from "gamed", concentrating result emission into one project-owned script is a **net loss of integrity** vs today's N-file surface. | Run the consumer's smoke target and see what `_count_e2e_tests` (`gates.py:899`) reports. **30 minutes.** If ambiguous: require scoped runs to declare `scope:` in the result file. |
| 3 | **Can the consumer's `db:reset` take a target-DB argument?** All of Phase 2 assumes it can be parameterized. | Read the script. **10 minutes.** Nobody has. |
| 4 | **Is teardown survivable under `SIGKILL`?** | If per-worktree DBs can leak on crash, **abandon per-worktree DB isolation** and serialize DB-touching changes instead — `profile_loader.py:181` already has the `serialize` directive, it is far cheaper, and it costs only parallelism. **I would rather ship correct serialization than a leaky provisioner. Kill signal: the first orphaned database.** |
| 5 | **Does a second consumer exist to validate against?** Everything here is **n=1, on the same stack that produced the bug**. | Scaffold a throwaway Python/pytest service and run one change through it. **1 day — the cheapest insurance in this document.** If consumer #2 needs the schema *restructured* rather than *extended*, ship Phases 0–2 only (they are pure bug fixes and stand alone) and defer 3–6. |
| 6 | **Will `contract.yaml` become the 7th dead extension point?** The precedent is grim: the `project-type.yaml` override surface has 5 keys and **0 were used in 2 months**; `detect_schema_provider` (`profile_types.py:215`) is implemented and **never called**; 6 hooks have zero callers. | **The answer here is genuinely different, and it is the strongest argument in the study: `contract.yaml`'s keys map 1:1 onto artifacts the consumer has ALREADY BUILT BY HAND** — gate scripts, ratchet baselines, a result file, `db:reset`, `db:seed`. **The adoption evidence exists before the feature does.** The old surface went unused because it was orthogonal to the pain, not because consumers are lazy. **Kill signal: `checks:` is empty for two consecutive consumers.** |

---

## 8. In one line

**The project owns the command. set-core owns the verdict — and a verdict needs facts, not an exit code.**
A fourth project type would have delivered the delegation and thrown away the framework, silently, while printing a
green health line.
