# Should set-core Drop Git Worktrees? — A Feasibility Study

**Date:** 2026-07-14
**Method:** 45-agent research workflow (coupling map → bug attribution → 4 competing designs → adversarial refutation)
**Trigger:** `lib/set_orch/engine.py:62` defaults `max_parallel: int = 1`. Parallelism is the only thing a worktree
buys over a plain branch — and it is switched off. So we are paying the full complexity cost of an unused feature.
**Companion:** [`orchestration-postmortem-2026-07-14.md`](orchestration-postmortem-2026-07-14.md)
**Status:** decided — **keep worktrees, fix the wiring.** Remediation not yet started.

> Consumer project names are omitted per `CLAUDE.md`. Evidence is reproducible from the orchestration artifacts
> any consumer project emits.

---

## 1. The answer

**No. Do not remove the worktrees — and the lobotomy would not have fixed the thing that hurt.**

The worktree is a **directory**. The pain came from a **branch**, a **gate**, and a **bug**, and all three survive
the removal intact. Worse: the fix worth ~45% of the token burn is **already written, already hardened, already
tested, and simply not wired up.** We were about to spend ~8,000 LOC of churn to work around a dead flag.

**Correct scope: fix the gate wiring (~40 LOC), then measure, then decide.** Keep worktrees. Reject the symlink.
Reject sparse-checkout.

---

## 2. Attribution — where the run's 14.77M tokens actually went

The tempting causal chain is *worktrees → merge boundary → integration e2e gate → token burn*. **It breaks at link
two.** The merge boundary is created by the `change/<name>` **branch**, not by the directory it is materialised in.
Branch-per-change appears at ~29 sites (`merger.py:625,778,925,937,1087,2590,3283`; `dispatcher.py:1306,1635,1646,2936`;
`engine.py:691`; `recovery.py:340,368`) entirely independent of worktree code. **Delete every worktree, keep the
branch, and you still have `_integrate_for_merge` (`merger.py:1379`), `_run_integration_gates` (`merger.py:1686`,
796 LOC), the ff-only merger — and the burn.**

| Root cause | Site | Share of observed cost | Killed by removing worktrees? |
|---|---|---|---|
| **Integration e2e gate blames the change for `main`'s pre-existing failures** | `merger.py:2005` hand-rolls `run_command(["bash","-c",smoke_cmd])`, bypassing the gate registry | **~45%** (worst change: 6,580,209 tok = 44.6%; **20 of 22** `CHANGE_REDISPATCH` carry `reason=integration_e2e_failed`) | **NO** |
| **Merge-boundary mechanics** — conflicts on cross-cutting files; **26 of 37 `MERGE_ATTEMPT`s failed (70%)**; **5/5** `FIX_ISS_ESCALATED` were `merge_stalled`; 17.8% of commits pure integration ceremony; one commit deleted 829 duplicated lines of a seed file | `merger.py:718` `_apply_merge_strategies` — writes nothing, because `merge_strategies()` returns `[]` and **no module overrides it** | **~20%** | Only if you also delete the **branch** |
| **Wrong integration branch** — two independent detectors (`subprocess_utils.py:439`, `bin/set-merge:36`) both hardcode `main`/`master`; the consumer's trunk was not `main`. set-core merged the wrong ref into change branches, dragged in a stale commit, and permanently broke `--ff-only` for one change (`ff_exhausted_no_issue`) | `merger.py:2775` → `detect_default_branch()` | **~8%** (one change lost outright) | **NO** — any design that merges anything inherits this |
| **Uncapped recovery loop** — `_recover_integration_e2e_failed` resumes changes with **no `max_parallel` check** (the cap is enforced only at `:3940`/`:4470`), so retries interleaved | `engine.py:2901-2946` | **~5%**, and **a confound on every other number in this debate** | **NO** |
| **Port collisions / zombie servers** — real, not theoretical (`... is already used` in a change's `last_retry_context` → gate fail with unparseable output → full agent redispatch). The `e2e_port_base` directive (`engine.py:101`) is **declared, parsed, schema'd, documented — and has zero readers** | `project_type.py:1880` (`md5 % 1000 + 3100`) | **~5%** | Partially |
| **Circuit breaker wired to the wrong status** — `merger.py:2711` aborts after 3 identical gate hashes, but only `if change.status == "merge-blocked"` (`merger.py:2709`); the burning loop sets `integration-e2e-failed`. **The brake exists and was never connected to the wheel** | `merger.py:2709` | amplifier on row 1 (8 retries instead of ~3) | **NO** |
| **Worktree-*directory*-specific cost** — N checkouts × ~1 GB, duplicate worktrees, one redundant e2e run per change, ~95 LOC of collision logic | `dispatcher.py:2880-2975`, `bin/set-new:233-240` | **~5–8%** (provisioning ≈ 6.7 s/change ≈ 1.5 min of a 17.5 h run) | **Yes** |

### The crux

> **The worktree *directory* owns ~5–8% of the pain.**
> **The branch / merge boundary owns ~28%.**
> **A single un-wired gate flag owns ~45%.**

### Two numbers that did not survive audit

- **"95% of tokens burned in redispatch loops" — FALSE.** That was top-3 *concentration*, not redispatch cost.
  Two of the three heaviest changes recorded **zero** `CHANGE_REDISPATCH` events, and one change with **7**
  redispatches burned only **76k tokens**. The defensible figure is **~45%**.
- **"Port collisions cost nothing" — also FALSE.** The grep found zero because gate stdout is not in the events
  stream, and the runner's message is `"is already used"`, not `EADDRINUSE`.

---

## 3. What the worktree uniquely buys

| Property | Verdict |
|---|---|
| Branch isolation (agent commits cannot touch main) | **The BRANCH buys this, not the directory.** |
| Discardability of a failed change | Switched **off** — `_resolve_retention` (`merger.py:635-653`) defaults to `"keep"`. |
| Crash recovery / resumability | **A net liability.** `recovery.py:334-343` builds a `worktrees_to_remove` list; `reset_change_to_pending` (`recovery.py:564`) clears `worktree_path`. Recovery rests on commits + `orchestration-state.json` + a safety tag — all of which survive a single checkout. |
| Forensics (post-mortem tree) | **~80% already decoupled** — `_archive_worktree_logs` (`merger.py:267`), `_archive_test_artifacts` (`merger.py:299`) copy everything out *before* cleanup. |
| **Parallelism** | **Provably zero.** `max_parallel=1` (`engine.py:62`), never overridden. The one thing a directory buys over a branch — switched off. |
| **A human can use the repo while an agent works** | **REAL and irreducible.** It is not implemented anywhere — it *is* the directory. The agent's builds, its test web server, and its destructive schema pushes all happen somewhere that is not your checkout. |

### The decisive question: with no merge, where do integration gates run?

**No design answered this convincingly, and the code actively refutes the easy answer.**

1. **The gate is directory-conditional, not branch-conditional.** `execute_merge_queue` reads
   `wt_path = change.worktree_path or ""` (`merger.py:2571`) and gates the *entire* integration path behind
   `if wt_path and os.path.isdir(wt_path) and not ff_exhausted:` (`merger.py:2613`). **No directory → no gates →
   straight to ff-merge** (`merger.py:2657`).
2. **`git worktree` is *in* the gate path.** `merger.py:2589-2594` logs verbatim: *"Worktree missing for %s — cannot
   run integration gates. Recreating worktree for gate execution"*, then runs `git worktree add`. set-core asserts
   in its own prose that gates cannot run without one.
3. **A symlink is not a worktree.** Verified: `git rev-parse --show-toplevel` through a symlinked path returns the
   *real* path; `git worktree list` does not list it; there is no second HEAD or index. `bin/set-merge:1110-1127`
   hard-requires a registered worktree, and `bin/set-common.sh:376` **explicitly skips the project root** when
   scanning. **Every isolation guard would silently pass while providing no isolation.**

---

## 4. The four designs

Survival after adversarial refutation (three lenses per load-bearing claim: code, failure-modes, regression-detection):
**Thin worktrees 50% · Keep-and-fix 33% · Trunk-only 33% · Single-checkout ~15%.** *(One design agent died on an API
error mid-run; its design was reconstructed from the surviving probes and scored, but with lower confidence.)*
**Nothing scored well. The winner wins on the merits, not on the vote.**

**Design 1 — Keep the worktree, fix the gate.** *Right conclusion, wrong mechanism, wildly overstated effort.*
Its diagnosis holds, but its load-bearing evidence — *"`grep baseline lib/set_orch/` = 0, therefore no baseline
exists"* — is **refuted by three independent probes**. A full, hardened main-baseline compare **already ships**
(see §5). Design 1's proposed ~250 LOC Layer-1 module would ship a **third** baseline implementation, put
runner-shaped failure parsing into Layer 1 (violating `modular-architecture.md` rule 1), and create two caches that
disagree at 3am. **The real fix is ~40 LOC of wiring.**

**Design 2 — "Thin worktrees" (sparse-checkout + shared store).** *Headline unsafe; one buried finding is the best
thing in the corpus.* The speedup reproduces (`--no-checkout` + sparse = **0.23 s / 48 MB** vs **3.6 s / 1010 MB**) —
and it is **unsafe on the one real consumer**, because its docs tree is a **runtime input** read by three routes and
asserted by two smoke tests. Excluding it makes those tests **fail in every worktree and pass on main** —
manufacturing a new, permanent instance of the *exact* misattribution bug that cost 44.6% of the run. `build` passes
anyway, so the design's own safety check is blind to its own defect. A conflict inside an excluded path also
**deadlocks the pipeline**: `git add` exits 1 (*"paths exist outside of your sparse-checkout definition"*), the merge
returns `conflict`, and `_handle_merge_conflict` (`merger.py:3263`) dispatches an agent to rebase a file it cannot
see and cannot stage. **And the 26× figure measures the consumer's repo hygiene, not worktrees** — a full
`git worktree add` on set-core itself is **0.41 s**; in the consumer, one `.mp4` accounted for **663 MB** of the tax
(and it is the same stale blob that broke the ff-merge).

**Design 3 — Single checkout, branch per change, checkout-switching.** *Viable, not cheap, buys nothing.*
It **keeps** the branch, the merge queue, `_integrate_for_merge`, the integration gates and the ff-merger — therefore
**keeps the ~45% burn**. It requires `main` and `change/<name>` checked out in the same directory simultaneously
(`_integrate_for_merge` merges into the change branch at `cwd=wt_path`, `merger.py:1414`); **git forbids it** —
~300–400 LOC of stash/checkout dance, reintroducing every dirty-tree hazard. It **deletes the gate sandbox** (your
checkout would sit on a change branch, mid-build, mid-test-run, while your dev server and editor read it), and it
silently breaks the three modules that parse `git worktree list --porcelain` as source of truth
(`recovery.py:172-194`, `reconciliation.py:148-169`, `change_cleanup.py:44`).
**Cost: ~25 production files, ~1,000 LOC Python + ~1,600 LOC bash. Benefit on the actual pain: zero.**

**Design 4 — Trunk-only.** The only design that genuinely kills the merge boundary. It also costs **~8,000–10,000
LOC of churn** including **8 breaking removals from the `ProjectType` ABC** (the public Layer-3 plugin contract),
**does not delete the gate** (it relocates it: same 796 LOC, worse rollback), **destroys blast-radius containment** —
the one thing branches actually buy at `max_parallel=1` — and **still does not fix the baseline bug**: the gate would
fail on main's HEAD instead of on the merged tree and blame the same innocent change.

---

## 5. The finding that reframes everything: the baseline already exists

**`modules/web/set_project_web/gates.py:1002` — `_get_or_create_e2e_baseline()`** runs the suite on `main`, caches the
failing-test set to `set/orchestration/e2e-baseline.json` **keyed on main's SHA**, auto-invalidates when main moves
(`gates.py:1034`), guards races with `fcntl.flock`, uses a dedicated port (`_E2E_BASELINE_PORT`, `gates.py:59`), and
has a dirty-root guard. **`gates.py:1717` computes exactly the right thing:**

```python
new_failures = wt_failures - baseline_failures
if not new_failures:
    return GateResult("e2e", "pass", ...)   # only pre-existing failures — not this change's fault
```

It has **11 unit tests** (`tests/unit/test_e2e_baseline_cache.py`) and was hardened **two months before the run**.

**The bug is a dead flag.** `GateDefinition.run_on_integration` (`lib/set_orch/gate_runner.py:115`) is set `True` on
the web e2e gate (`modules/web/set_project_web/project_type.py:1395,1432,1454`), the archived design specified the
wiring — and **`grep -rn run_on_integration lib/ modules/` finds no reader.** `merger.py` imports only `GateResult`
from the registry (`merger.py:1701`) and **hand-rolls a second, baseline-blind copy of the e2e run** at
`merger.py:2005`/`:2160`/`:2172`. Its own docstring admits it (`merger.py:1693`): *"Uses lightweight subprocess calls
(not the full gate executors...)"*.

**So the pre-merge gate is baseline-aware and the integration gate is not.** That is the whole disaster.

---

## 6. Remediation — ~440 LOC, ~1.5–2 weeks, zero breaking API changes

| # | Fix | Target | Effort |
|---|---|---|---|
| **0** | **Wire `run_on_integration`.** Make `_run_integration_gates` execute the registry's `run_on_integration=True` gates instead of hand-rolling bash. This activates the **already-shipped, already-tested** baseline compare at the merge boundary. | `merger.py:1929-2210`; a reader for `gate_runner.py:115` | **~40 LOC, 1 day** |
| **1** | **Connect the circuit breaker.** Fires on 3 identical gate-output hashes but is gated on `status == "merge-blocked"` while the burning loop sets `integration-e2e-failed`. **One predicate.** Would have cut the worst change from 8 retries to 3 on its own. | `merger.py:2709` | **1 line, 1 hour** |
| **2** | **Cap the recovery loop at `max_parallel`.** Until this lands, *"we already run sequentially"* is false and every measurement is confounded. | `engine.py:2901-2946` | **~30 LOC, 0.5 day** |
| **3** | **One integration-branch resolver.** Add an `integration_branch` directive, resolve **once** at init, snapshot into `state.extras`, route `_get_main_branch()` through it, pass `--to <branch>` (already supported at `bin/set-merge:1141`). Assert pre-ff that the ref merged in == the ref merged into. Kills the entire stale-ref class. | `merger.py:2775`, `merger.py:1068`, `bin/set-merge:36` | **~60 LOC, 1 day** |
| **4** | **Per-change database.** `ENV_FILES` (`dispatcher.py:759`, `:1075-1080`) copies `.env` verbatim into every worktree — so **every worktree inherits the same `DATABASE_URL`**, and `integration_pre_build` then runs a destructive schema push (`project_type.py:2008`) **against the database the developer's own dev server is reading**. Add `worktree_env_overrides(change_name)` to the ABC (additive, default `{}`), apply where `PORT` is injected today (`dispatcher.py:1104-1119`), implement per-change schema in `modules/web`. **Highest-severity infra bug in the codebase; never named before.** | `dispatcher.py:759`/`:1075`, `project_type.py:2008` | **~120 LOC, 1–1.5 days** |
| **5** | **Ports.** Wire `e2e_port_base` (`engine.py:101`) — declared, parsed, documented, **zero readers**. Have `worktree_port` (`project_type.py:1880`) skip a reserved set (the dev port, the baseline port, milestone ports). Also `_kill_stale_listeners_on_port` (`gates.py:1175`) SIGKILLs *whatever* holds the hashed port with **no ownership check** — a change that hashes onto the dev port murders the dev server. | `project_type.py:1880`, `engine.py:101`, `gates.py:1175` | **~40 LOC, 0.5 day** |
| **6** | **Load the merge-strategy weapon.** `merge_strategies()` (`profile_types.py:707`) returns `[]` and **no module overrides it**; its mapping is broken anyway (`"theirs"` → driver `merge=ours`, `merger.py:733-737`). Add `regenerable_paths()` to the ABC, declare the e2e manifest regenerable (the regenerator already exists), auto-resolve regenerable conflicts, add a post-merge `<<<<<<<` scan (would have caught the 829-line seed duplication). | `merger.py:718-760`, `profile_types.py:707` | **~150 LOC, 2–3 days** |

**Compare: ~8,000–10,000 LOC and 8 breaking ABC removals for the lobotomy.**

### Explicitly do NOT do

- **Do not symlink `node_modules`.** Reproduced destruction of the root tree: a non-interactive install in a worktree
  whose `node_modules` symlinks to root prints *"will be removed and reinstalled from scratch ‣ true"* and **does it**
  — the root lost a package and `require()` broke. Independently, the generated Prisma client lives *inside*
  `node_modules/.prisma`, so a shared tree gives every worktree **the last writer's schema**. Either leg alone kills it.
- **Do not share the build cache.** Measured across 55 production builds: warm builds are **12% SLOWER** than cold
  (16.7 s vs 14.9 s); the cache is <1% of the build output directory.
- **Do not sparse-checkout the docs tree** — it is a runtime input on real consumers (see §4).
- **Do not symlink the worktree** — git resolves it away and every isolation guard silently passes while providing none.
- **Do** purge large binaries from the repo (one 663 MB `.mp4` was ~2/3 of the entire per-worktree tax — **and the same
  stale blob broke the ff-merge**). That is repo hygiene, free, and orthogonal to architecture.

---

## 7. The order argument (non-negotiable)

Every number in this debate is poisoned by three confounds:

1. The integration gate blames innocent changes → **every failure count is inflated**.
2. The recovery loop ignores `max_parallel` → **set-core has never actually run a sequential orchestration.** An
   unknown fraction of the merge conflicts attributed to worktrees came from unintended concurrency in a run believed
   to be serial.
3. The integration branch resolved to the wrong trunk → one change was destroyed by a bug unrelated to any of this.

**Doing the lobotomy now means comparing a poisoned baseline against an unpoisoned one and crediting the architecture
with the fix. You would learn nothing, and you could never undo it.**

---

## 8. The experiment that settles it

**Ship fixes 0 + 1 only (~41 LOC, one day). Re-run the identical spec. Compare four numbers — thresholds stated
before the run:**

| Metric | Baseline (the June run) | Kill threshold |
|---|---|---|
| `CHANGE_REDISPATCH` with `reason=integration_e2e_failed` | 20 of 22 | **< 5** |
| Total tokens | 14,766,363 | **< 9M (−40%)** |
| `MERGE_ATTEMPT : MERGE_SUCCESS` | 37 : 11 (30%) | > 60% |
| `FIX_ISS_ESCALATED` with `merge_stalled` | 5 of 5 | ≤ 1 |

**If redispatches drop below 5 and tokens fall 40%+ → the worktree was never the problem, the case is closed, and it
cost one day instead of two months. If they do not move → the merge boundary itself is the irreducible cost, and the
lobotomy case becomes genuinely strong.** Either way the answer comes from data, not from argument.

**Pre-flight regression test (must go RED before fix 0 lands):** seed a repo where `main` is red on spec X; dispatch
a change that does not touch X; assert that today's `_run_integration_gates` marks it `integration-e2e-failed`.
Without it, none of this is falsifiable.

## 9. The deferred decision

Once the run is clean, **raise `max_parallel` to 2 exactly once.** That is the experiment that decides whether the
worktree earns its keep.

- **It works** → we get the parallelism the worktree machinery was built for, and the question is settled in favour
  of keeping it.
- **It fails** → the benefit numerator is permanently zero, and the honest endgame is **not a lobotomy but a
  demotion**: keep exactly two worktrees — one pinned baseline worktree for the main-baseline suite, and one created
  *only on gate failure* for post-mortems. That deletes `bin/set-new` (486 LOC), `bin/set-close` (293 LOC) and the
  `dispatcher.py:2880-2975` collision block, while keeping the branch, the merge queue and the gate — which were never
  the worktree's doing.

**That path is still fully available after the fixes. It is not available after the lobotomy.**
