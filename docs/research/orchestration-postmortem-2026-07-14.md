# Orchestration Post-Mortem: What a Six-Week Consumer ERP Run Taught Us

**Date:** 2026-07-14
**Method:** 77-agent research workflow (forensics → landscape → strategy panel → adversarial refutation)
**Source:** a consumer ERP/commerce project, ~1,800 commits over 6 weeks; one full orchestration run
followed by five weeks of manual OpenSpec work
**Status:** findings accepted; remediation not yet started

> Consumer project names are deliberately omitted. All evidence below is reproducible from the
> orchestration artifacts (`orchestration-events*.jsonl`, `orchestration-state.json`,
> `orchestration-plan.json`, `state-archive.jsonl`) that any consumer project produces.

---

## 1. The question we asked

The consumer team's own hypothesis was: *"we did not know what LEVEL of specification set-core needs
in order to work well."* They had abandoned orchestration after one run and reverted to hand-authoring
OpenSpec changes. Four questions followed from that:

- **Q1** — can set-core orchestrate coarser **feature groups** without OpenSpec artifacts as the input unit?
- **Q2** — should domain experience be distilled into the **template / IKP** system instead?
- **Q3** — was greenfield generation the wrong start; should we **decode donor codebases** into templates?
- **Q4** — is set-core worth evolving, or does the methodology need replacing?

## 2. The verdict

**The spec-level hypothesis is wrong on the premise and half-right on the consequence.**

The input to `decompose` was **not** thin. It was a 10-file, ~5,900-line, 338 KB structured spec suite
containing a 1,026-line data model (21+ entities), a 792-line UI spec (27 screens) and 417 lines of
numbered test scenarios. The digest mined **47 requirements / 212 acceptance criteria / 8 ambiguities**
out of it. That is at or above the level set-core is designed for.

What is true is that the team wrote such a spec **exactly once**. It cost nine days. The next two
milestone specs were **50 and 75 lines**, and the ~100 changes that followed ran against no spec at all.
**The binding constraint is spec-authoring bandwidth, not spec-level knowledge.**

### The causal chain

1. **The engine ran once, for ~19 hours** (a single day, not the assumed ten). It merged **14/18 changes**,
   covered **38/47 requirements (81%)**, and produced **315 code files of which 300 (95%) still exist today**.
   **63% of all file modifications in the following month landed on orchestrator-born files.**

2. **The digest discarded ~93% of the spec before any agent saw it.** 338 KB in → 24 KB of requirement
   prose out (**~519 bytes per requirement**). Worse, dispatch diluted it further: agent briefs were
   50–63 KB, of which the change's own **Scope was 1.2–2.6 KB (2–4%)**, while the single largest section in
   every brief was a generic ~12 KB "Review Learnings Checklist"
   (`orchestration-state.json` → `changes[].input_md_breakdown`). **Agents saw ~1–2% of the spec.**

3. **Intent enforcement was off; compilation enforcement was maximal.** The project's
   `directives.gate_overrides` set `spec_verify: soft` for `feature`, `foundational` and `infrastructure`.
   Event census: `build` 68 starts / 13 blocking failures; `e2e` 44 starts / 23 blocking failures;
   **`spec_verify` never blocked once.** The 8 detected ambiguities — including a flat contradiction between
   two spec sections on reservation timing — went to `digest/triage.md` with **all 8 `**Decision:**` fields blank**,
   and planning proceeded anyway.

4. **So the gates passed mocked UIs.** A clause-level audit the next day scored 1,050 spec clauses:
   **72.7% implemented, 33 WRONG, 23 STUB, 103 PARTIAL, 98 MISSING.** Coverage collapses along the
   declarative→procedural gradient: **data model 93.5% → UI specs 75.0% → order processing 58.4% →
   payment matching 48.7%.** The e2e manifest bound **45 requirement ids against 1,050 clauses = 4.3% granularity**.
   **45% of the orchestration-era changes (30/66) were repairs of the orchestrator's own output.**

5. **And the run collapsed on something unrelated to all of the above.** ~36 smoke tests were **already failing
   on `main`**, and **the integration e2e gate never applies the main-baseline compare** (see the correction below —
   the baseline exists; the integration path bypasses it). Every change was therefore blamed for pre-existing
   failures and redispatched to "fix" tests it had never touched, up to the retry limit. **20 of the 22
   `CHANGE_REDISPATCH` events carry `reason=integration_e2e_failed`**, and the worst offender —
   `ai-order-processing`, 8 redispatches, hitting the limit — consumed **6,580,209 of 14,766,363 tokens (44.6%)**.
   The supervisor diagnosed the cause correctly five times and asked for exactly the right fix.

   > **Correction (2026-07-14, from the follow-up worktree study).** An earlier draft of this document claimed
   > *"14.04M of 14.77M tokens (95%) burned in redispatch loops"*. **That is false, and it must not be reused.**
   > It was top-3 *token concentration*, not redispatch cost: the other two heavy changes
   > (`order-state-machine` 3.88M / 26.3%, `email-intake-pipeline` 3.58M / 24.3%) recorded **zero**
   > `CHANGE_REDISPATCH` events, and `ai-assistant` burned only 76k tokens *despite* 7 redispatches.
   > The defensible figure for gate-churn cost is **~45%**, not 95%.

### The two findings that hurt

**Abandoning orchestration made rework worse.** Fix-shaped commits: **33.8% in the orchestrated era →
42.6% in the manual era**. And the rework changed *kind*: from cheap machine-caught gate failures to
expensive semantic misses discovered in production (the manual era shipped several wrong-monetary-amount
defects to external partners). Note also that **68% of the "manual" commits carry a Claude co-author trailer** —
so the real comparison is *unattended agents vs attended agents*, and the attended loop costs a human's full
attention for a month **and** has the higher rework rate.

**Conformance and correctness are orthogonal.** The spec file the agents conformed to best — the data model,
at **93.5%** clause coverage — specified money fields as **integer**. The agent implemented them as `Int`,
**exactly as told**. That single decision is the root of a ten-change, month-long, still-open pricing rework
chain. **Tripling the spec would only have produced a three-times-more-precisely-specified wrong money model.**

---

## 3. Answers

### Q1 — Feature groups without OpenSpec? *The question was already answered by the data.*

set-core **never orchestrated per-OpenSpec-change.** The run's event log contains **17 change names for
47 requirements** — `auth-and-foundation`, `pricing-and-calculations`, `order-state-machine`,
`invoicing-and-documents`, … Those **are** feature groups. The ~80 capability specs were the **output**,
not the input unit. And `lib/set_orch/engine.py:62` already defaults `max_parallel: int = 1`.

- **Delete the artifact stage from the input path: yes.** `lib/set_orch/loop_prompt.py:65-90`
  (`detect_next_change_action`) returns `ff:<name>` → an agent writes proposal/design/tasks and *does not
  implement*; then `apply:<name>` hands off to a second agent. That is a context-losing handoff, and set-core
  already spends code defending against it (`dispatcher.py:2875` on re-running `/opsx:ff` burning 80k+ tokens;
  `engine.py:2399` explicitly ordering agents *not* to recreate the artifacts). In the consumer project ~80% of
  the AI-written specs were **never reviewed**, one change was implemented and archived **twice, byte-identical,
  a week apart**, and 20% of manual-era commits were pure `openspec/` filing overhead.

- **Make the unit bigger: no.** METR (arXiv 2503.14499, R²=0.83) finds task length is the dominant predictor of
  agent failure, and the 80%-reliability horizon is far shorter than the 50% one. The run agrees: the three
  largest changes consumed 95% of the tokens.

- **Change the unit's SHAPE: yes.** `lib/set_orch/planner.py:720` (`auto_split_change`) groups by the **first two
  path segments** — i.e. by directory. That makes slices *screen-shaped*. The consumer's bugs are
  *invariant-shaped*: one derived quantity implemented inline in 13+ places, one deadline rule implemented four
  different ways, ~47% of reserved stock units orphaned on closed orders. **No screen-shaped change ever owns
  "the money model", so every screen ships its own local rule and N inconsistent rules accumulate.**
  Re-key the splitter to requirement-**domain** affinity (the digest already tags every requirement with a domain).

### Q2 — Distil into templates / IKP? *Partly — and the naive version is already refuted.*

By name, the consumer's ~160 capability specs partition as **universal plumbing 26% / generic ERP 51% /
country-regulatory 5% / client-unique 18%** — 82% "templatable". **That number is a trap.** Token-scanned,
only **~26% of the "generic ERP" specs** are free of client- and regulatory-specific tokens (the canonical
pricing spec has the local 27% VAT rate baked into its scenarios). **~13% of spec text is genuinely reusable.**
A template can ship the **shape**; it cannot ship the **text**.

**And prose rules demonstrably do not bind.** `modules/web/set_project_web/templates/nextjs/rules/transaction-safety.md`
contains exactly the right rules — *Atomic Finite Resource Operations*, *Server-Side Price Recalculation*,
*Single Source of Truth for Validation*. It **was** injected into agent briefs (rendered as
`# Transaction Safety Patterns` §1–§6 in the archived `input.md` of a change from the run). The agents read it
and shipped an atomic-finite-resource bug and a server-side-recalculation bug anyway. The consumer's own
retrospective states it plainly: **a rule is not a rule because it is written down; it is a rule because it runs
and fails.**

**What is worth distilling, ranked:**

1. **A regional compliance pack (IKP).** ~5% of capabilities, ~100% reusable, needed verbatim by every
   same-jurisdiction bid: e-invoicing integration + policy (not just API surface), business-day/holiday
   calendars, credit-note/storno semantics, VAT rounding policy. The existing IKP packs are **all integration
   packs and zero policy packs** — that is the gap.
2. **Invariant packs — as EXECUTABLE GATES, not prose.** Six families, each traceable to a production incident
   and none client-specific: derived-state single-writer; money precision & rounding; document
   immutability/versioning; cross-surface consistency; temporal/locale semantics; modelling shape
   (fee-as-line-item, never a column). Keyword growth in the consumer's specs, normalised against 2.86× baseline
   growth: *idempotent* 0→30, *transaction/atomicity* 16.4×, *audit* 9.6×, *storno* 7×, *rounding* 6.8× — while
   *VAT* grew only 2.4×, **below** baseline. **What was missing was never domain facts. It was cross-cutting
   correctness invariants.**
3. **One schema-shape rule, free, deployable today:** client-specific brands/categories were emitted as
   **DDL-level Postgres enums**. A template must express client variability as **seeded lookup tables, never
   enums** — otherwise every new client forks the schema.

**Honest sizing of the payoff:** the differentiating business logic is **6.4% of `src/`**. **93.6% of what was
written is not the client's competitive advantage.** That is the strongest argument for template/IKP investment —
*and also the strongest caveat*, because that 93.6% is exactly the part orchestration already produced correctly
in a day.

### Q3 — Was the starting direction wrong? Should we decode donor codebases? *No.*

Nothing in the consumer's ~170-change archive is of the form *"we did not know an ERP needs X."* Every critical
failure is a **consistency** failure — a value written in two places that drifted. **Zero missing-feature failures.**

And the decisive number: **client-unique capabilities tripled after orchestration ended** (7 during the run → 21
in the manual era). They were discovered by iterating with the client **against running code**, and no donor
codebase supplies them. Likewise **68% of the recorded product decisions postdate the run**. That cost is
irreducible in client work.

**Where donors are still worth reading — knowledge only, never code:** the official e-invoicing schemas and a
mature ERP's *document-lifecycle ontology* (quote → sales order → delivery note → invoice → credit note, stock
ledger, commissions). Deliberately pick a donor on the **wrong stack** so there is zero temptation to import code.
Prior art (Thoughtworks CodeConcise) shows AI-assisted decoding cuts comprehension time substantially but **stops
at comprehension** — it has never been shown to generate templates. **Do not start a decode project.**

### Q4 — Evolve set-core or replace it? *Evolve. It is not close.*

- The run produced **95% durable code** and the structural spine still being edited a month later.
- It reached **72.7% of a 1,050-clause spec in ~19 hours, unattended, at `max_parallel=1`.**
- Abandoning it made rework **worse** and moved it from machine-caught to production-caught.
- Everything it collapsed on is a **named, bounded engine bug**, and the supervisor found and filed all of them
  for free: no e2e baseline compare; merge-time conflicts on cross-cutting files; an FF-merge of a stale
  non-main commit that permanently broke `--ff-only` for one change; and a review gate that **wrote findings to a
  file without applying them while still marking the change done**.
- **The experiment was confounded:** spec-read-first and knowledge injection landed **during the run**. The very
  first change — the one that laid the schema, auth and the pricing base that every money bug traces back to —
  was dispatched with a **334-line brief containing zero spec references**. Later changes in the same run got
  843–1,075-line briefs with 2–5 spec references. **Nobody has ever run decompose→dispatch with the repaired
  pipeline, not once.**
- **Externally, nobody is doing better.** Reported experience with fixed-ceremony SDD tools is a small bug fix
  ballooning into "4 user stories with 16 acceptance criteria"; spec-kit users report the artifacts *"create the
  illusion of work"*; the most spec-maximalist vendor never shipped GA and pivoted. **One 19-hour run at 72.7%
  clause coverage is above the industry norm, not below it.**

---

## 4. What survived adversarial review

Five strategies were argued at full strength and attacked by three independent skeptics per load-bearing claim
(evidence lens, engineering lens, delivery-pressure lens). Survival: 33% / 25% / 8% / 0% / 0%. **Every strategy
whose deliverable was more text scored zero.** Three interventions survived:

1. **Adversarial review against CODE, before implementation.** Measured on one consumer change: a spec built from
   a 3-subagent code map, a measured vendor spike, 10 delta specs and a green `openspec validate` still yielded
   **4 CRITICAL + 8 SERIOUS** findings — including a plan that would have re-created the very bug it was written
   to fix. The team's own note: *none of it was visible from reading the spec; all four came from the code.*

2. **A `stub_check` static gate.** Verified by *replay* against the tree at the last engine merge: signature
   matching (`setTimeout` near `toast`, `onClick={() => { toast`, hard-coded constant arrays `.map()`'d into JSX,
   mock service classes, literal placeholder comments) reproduces the audited STUB findings ~1:1 and even catches
   ones the LLM audit missed, at one false positive in 249 files.
   **Non-negotiable caveat:** it **must be change-scoped with a main baseline**, or on day one it fires on
   pre-existing debt and reproduces the exact false-positive wall that killed the run. **This is the same missing
   baseline primitive as the e2e gate — build it once, use it twice.**

3. **Executable invariant tests against a real database** — the derived-state, money-precision and
   cross-surface families from Q2, as gates rather than prose.

**Killed by the panel:** an async "numbered-claims fact sheet" sent to the client for validation. The consumer
team *already built one* (592 numbered claims, client-requested) and the response rate is **0/592**. Base rate for
numbered-lists-awaiting-a-human in that project: **0-for-3** (8 triage ambiguities: 0 answered; 2 open questions:
0 answered). Meanwhile the client reverses semantics **five-plus times in five days** — every single reversal
sourced to a **live transcript**, never to an answered document. **The oracle is real and fast; the async channel
is the fiction.**

Also killed: the premise that intent-misses dominate the cost. Three independent classifications of manual-era fix
commits put intent misses at **33–42%**, with **~25% pure infrastructure/CI/deploy**, and only **~15%** of fixes
in a form a client could adjudicate *before seeing software*. The expensive defects were found by **adversarial
audit against code and production data**, not by asking anyone.

---

## 5. Remediation, sequenced

**Immediately — and before any other change, because nothing is measurable until this lands:**

1. **Wire `run_on_integration` so the integration gate uses the baseline that already exists.**
   **The baseline primitive is not missing — it ships and it is tested.** `modules/web/set_project_web/gates.py:1002`
   (`_get_or_create_e2e_baseline`) runs the suite on `main`, caches the failing-test set keyed on main's SHA,
   auto-invalidates when main moves, guards against races with `fcntl.flock`, and uses a dedicated port;
   `gates.py:1717` computes exactly the right thing — `new_failures = wt_failures - baseline_failures` — and passes
   the gate when the set is empty. It has 11 unit tests (`tests/unit/test_e2e_baseline_cache.py`) and was hardened
   **two months before the run**.

   **The bug is a dead flag.** `GateDefinition.run_on_integration` (`lib/set_orch/gate_runner.py:115`) is set `True`
   on the web e2e gate (`modules/web/set_project_web/project_type.py:1395`) — and **`grep -rn run_on_integration
   lib/ modules/` finds no reader**. `merger.py` imports only `GateResult` from the registry and **hand-rolls a
   second, baseline-blind copy of the e2e run** at `merger.py:2005` / `:2160` / `:2172`; its own docstring
   (`merger.py:1693`) admits it uses *"lightweight subprocess calls (not the full gate executors)"*.
   So the pre-merge gate is baseline-aware and the integration gate is not.

   **Fix: make `_run_integration_gates` execute the registry's `run_on_integration=True` gates instead of
   hand-rolling bash.** `merger.py:1929-2210`. **~40 LOC, one day.** Do *not* write a third baseline implementation
   in Layer 1 — that would put Playwright-shaped failure parsing in the core and create two caches that disagree.

   > **Correction (2026-07-14).** An earlier draft claimed *"the primitive does not exist"* on the strength of
   > `grep -rniE "baseline" lib/set_orch/`. **That grep was scoped to Layer 1 only and missed `modules/`.**
   > The claim was wrong, and it would have cost a ~250 LOC reimplementation of a working feature.

2. **Connect the circuit breaker.** It exists (`merger.py:2711-2721`, aborting after 3 identical gate-output hashes)
   but fires only `if change.status == "merge-blocked"` (`merger.py:2709`), while the burning loop sets
   `integration-e2e-failed`. The brake is built and not connected to the wheel. **One predicate.** On its own this
   would have cut the worst change from 8 redispatches to 3.

3. **Cap the recovery loop at `max_parallel`.** `_recover_integration_e2e_failed` (`engine.py:2901-2946`) resumes
   changes in a bare loop with no `max_parallel` check (the cap is enforced only at `:3940` and `:4470`). Retries
   therefore interleaved during a run believed to be sequential. **Until this lands, "we already run sequentially"
   is a false statement, and it is a confound on every other number in this study.** ~30 LOC.

4. **Promote adversarial-review-against-code to a core rule** (`templates/core/rules/`, deployed via
   `set-project init`). Zero infrastructure, already measured.

**This month:**

5. **`stub_check` gate** — static, change-scoped, main-baselined, in `modules/web/` (pure React/Next signature
   matching, zero domain knowledge, so it transfers to any web consumer unchanged). Wire
   `lib/set_orch/test_coverage.py:234` (`detect_stub_tests`) into the completion check so a mocked UI cannot report
   done. **Close the `gate_overrides` escape hatch** that let `spec_verify` go `soft` for feature/foundational/
   infrastructure — the fix is making it **non-overridable**, not flipping a default (`gate_profiles.py`
   `UNIVERSAL_DEFAULTS` already sets `spec_verify: "run"`).

6. **Wire `check_triage_gate` into the autonomous path.** It exists (`lib/set_orch/planner.py:1572`, raising at
   `planner.py:3206-3215`) but the engine can bypass it via `TRIAGE_AUTO_DEFER`. Eight ambiguities with eight blank
   decisions must not be a green light. **A config line.**

7. **Ship the first regional compliance IKP pack** (policy, not just API surface).

**This quarter:**

8. **Invariant packs as executable gates** against a real DB.
9. **Re-key `auto_split_change`** (`lib/set_orch/planner.py:720`) from path-prefix to requirement-domain affinity,
   so slices are shaped like invariant families rather than screens.
10. **Merge-time spec backflow** (next to `lib/set_orch/merger.py:531`): generate the capability spec from the
   merged diff plus green acceptance criteria. Humans author only the milestone spec and the decision records.
   Target the measured gap: **93% of the consumer's fix commits leave no trace in `openspec/` or the knowledge base.**
11. **Then, and only then**, re-run decompose on the repaired pipeline (spec-read-first from cycle 1,
   baseline-compared gates, `stub_check`, adversarial review) — **the configuration that has never been tested** —
   and compare against the June baselines: **72.7% clause coverage, 81% requirement merge, 45% repair-change rate,
   14.77M tokens.**

---

## 6. Open questions and the cheapest experiment for each

| # | Question | Cheapest experiment |
|---|---|---|
| 1 | Does a **richer** spec actually close the behavioural gap? Observationally the sign is **negative**: Spearman(lines-per-clause, coverage) = **−0.37** across the audited spec files; a 249-line spec scored 61.8% while a 1,356-line one (5.4× the text) scored 60.8%. | Dispatch one slice twice — once from the digest, once from a 3× richer hand-written section — identical gates, same clause audit. **~2 days.** Prediction: it does not move. |
| 2 | Is the manual era **repairing** the orchestrator's output or **building on** it? (95% file survival proves the files were not deleted, not that their contents were not rewritten.) **Most decision-relevant number still missing.** | `git blame` attribution of today's `src/` LOC to run-window vs post-run commits. **Half a day.** |
| 3 | Would `stub_check` + acceptance binding have caught the 103 PARTIALs? The STUB half is proven; the PARTIAL half is **not** — only ~21% look reachable by static + happy-path e2e. The remainder are semantic rule errors whose **claims were never made** (212 ACs against 1,050 clauses = a **20% binding ceiling** before any logic runs). | Replay the surviving `change/*` branches through the new gate and count against the audit. **2 days.** |
| 4 | Are the pre-existing smoke failures — the trigger for the entire collapse — **still failing**, or was the suite quietly abandoned? | Run the e2e suite on `main`. **10 minutes.** |
| 5 | Is the missing baseline the **whole** token story? Two "transient" failures the supervisor could not explain (a Playwright "No tests found" after 2.36M tokens; seed data not persisting into the integration gate's test env) smell like a **third distinct bug in the gate's environment bootstrap**. | Instrument the gate's env bootstrap; re-run one change. |

---

## 7. In one line

**set-core did not fail.** It ran once, for 19 hours, built 95% of the code still in use, and was defeated by a
main-baseline compare that **it already ships, already tests, and simply never calls at the merge boundary** — plus
a circuit breaker wired to the wrong status. The team then abandoned the only loop that made rework legible and
spent a month doing higher-rework work by hand. **Wire the gate, make the rules executable, ship the regional pack —
and stop trying to write a bigger spec.** The deepest spec ever written on that project is the one that told the
agent to store money in an integer.

---

## Related

- **In progress (2026-07-14):** a follow-up study on whether set-core should drop **git worktrees** entirely
  (`max_parallel=1` means the only thing worktrees buy over a plain branch — parallelism — is switched off).
  The decisive question that study must answer: **with no merge boundary, where do integration gates run?**
  Findings will be filed as a separate document.
- `.claude/rules/sentinel-autonomy.md` — the "never merge manually, gates only" rule this run repeatedly violated
  by hand-merging two changes.
- `docs/research/orchestration-output-divergence-2026-03-27.md` — earlier divergence work; the invariant-shaped
  bug class described here is its unresolved core.
