# Should there be a `set-factory`?

**Verdict: No — not now, and one third of it never.** The full dev+ops cycle does not belong in a new repo above set-core, and it does not belong crammed into set-core either. Build the cheap, compounding seams now (identity, versioning, naming); build the hotfix ADW only after set-core's own arc is closed and measured; delegate CI, promotion and release to the tools that already do them; and never build the meetings→requirements pipeline into the framework.

**Date:** 2026-07-19
**Method note:** This is a synthesis over six inputs — the author's own prior research on the software-factory frame; a stage-by-stage code audit of set-core; a stage-by-stage audit of the consumer project's working SDLC; three independently-authored architecture designs (separate layer / extend set-core / ports); and two adversarial reviews (premature-machinery, feasibility-and-scope). Claims are cited to `file:line` where they were verified in the working tree. Where the evidence does not decide a question, that is said out loud rather than papered over. The consumer project is referred to only as "the consumer".

---

## 1. What the factory idea actually is

The ambition, in the author's words, is a system one level larger in scope than set-core: continuous meetings with users → requirements → automatic implementation by agents → tests and gates → promotion through test/preprod → production, running across multiple projects continuously.

The prior art the author collected supports **part** of that, and it is worth being precise about which part.

**ADW (AI Developer Workflow)** is the unit: the classic SDLC pipeline where each node is now an agent *or* deterministic code, with the engineer appearing only at the two ends — prompting/planning at the front, reviewing/validating at the back. The source's own claim is deliberately deflationary about "loop engineering": the retry loop (gate fails → back to the build agent) is *one control-flow primitive inside* a workflow, not the workflow. Its sharpest operational rule is the separation mandate: *"You have to separate your code and your agents. Otherwise you just have an agent calling code."* And its reliability ordering — *"code is the most reliable by miles, followed by engineers, and then agents"* — is the load-bearing engineering claim in the whole corpus.

**The factory** is a *collection* of ADWs plus a **router that selects between them** (chore / bug / feature / hotfix), each with its own compute and model budget. *"You're not going to deploy your heavy AI developer workflows for a chore."* The router explicitly need not be an agent: *"This could just be a simple LLM call. This could be some deterministic code."*

Two things the sources do **not** contain, and this matters more than anything else in this section:

- **The factory begins at a ticket that already exists.** There is no requirements-elicitation stage anywhere in the source material. Continuous user meetings → requirements is not prior art; it is a novel extension the author is inventing.
- **The factory ends at "ship."** There is one CI/CD node. No environment promotion, no preprod, no multi-project operation. The only externally-sourced concrete instance (a large infrastructure company's published system) is a factory **for code review only**, CI-triggered, seven specialist agents behind a coordinator, ~$1 per merge request. Its own grade on self-improvement is F, on always-on C, and even its authors keep a "break glass" human override.

Provenance caveat, from the author's own research README: this is one content creator's video corpus; *"the useful core of the content is ~20% everywhere; the rest is product demo and self-promotion."*

### What the author's own plan already concluded — and deferred

The agent-system plan (v3, dated 2026-07-18) is not a factory plan; it is a review-agent plan. The factory frame enters at §11 as *input*, and it is handled with restraint that this document is going to endorse:

- **Confirmed, no action needed:** the software-factory / SDLC frame **is already** the set-core (agentic layer) ↔ consumer app (app layer) split. The OpenSpec chain *is* an ADW. Deterministic gates *are* the "code" actor. The named review agents *are* the "agents" actor.
- **The named gap:** *"our OpenSpec chain is ONE ADW (the feature path). By Dan's thesis this is correct but incomplete: we have no separate, lighter ADW for chore/hotfix, and no router that would decide by risk which to run and with what agent/model mix."*
- **The deferral, verbatim from the plan's final paragraph:** the pack-router *"could grow here (differentiated ADWs + factory-router), but that is a separate plan."* Filed on the README's *"radar, NOT urgent"* list, explicitly gated **after** a measurement not yet taken.
- **The net shipped output of that entire research effort was one file** — a runtime damage-control hook — described as *"the only concrete, drop-in-value piece from the research."*

**Read that sequence again, because it is the shape of the answer.** The author's own research concluded that (a) the factory frame is already satisfied by the existing split, (b) the one genuinely missing piece is a between-ADW router, (c) that piece is an *extension of an existing router*, not a new system, and (d) it is gated behind a measurement. Nothing in the author's own prior art asks for a new repo or a new layer.

---

## 2. What already exists, stage by stage

Twelve to seventeen stages depending on how you cut it. The honest picture:

| # | Stage | set-core | The consumer | Status |
|---|---|---|---|---|
| 1 | Requirements intake (meetings/users) | **Nothing.** Entry point is a hand-written `docs/spec.md`. `/set:write-spec` interviews *the developer at the terminal*, not stakeholders | Full: 24/7 capture of email/chat/voice/meetings → `inputs/` → `converted/` → `knowledge/`; 65 numbered decisions; knowledge→spec firewall | consumer-only |
| 2 | Backlog / prioritisation | **Nothing.** No backlog store, no cross-item ordering. Sequencing exists only *inside* one decomposed spec as a DAG | OpenSpec changes + backlog dir, human-ordered | consumer-only |
| 3 | Decompose spec → changes | **Fully owned. Strongest asset.** `/set:decompose`, `planner.py`, `digest.py`, typed changes with scope/complexity/deps/phase | uses set-core's or plain OpenSpec | **set-core** |
| 4 | Implement via agents | **Fully owned.** Worktree-per-change, per-change model routing, scope-matched `input.md`, design/IKP injection | — | **set-core** |
| 5 | Gates / tests | **Fully owned** — but see the dead/false column | 13 lefthook gate scripts, several with their own unit tests | **set-core** (+ consumer at commit time) |
| 6 | Merge | **Fully owned.** Serialized merge queue, integration gates, conflict auto-resolve | — | **set-core** |
| 7 | CI (remote) | **Zero.** No GitHub/GitLab integration, no PR creation, no status-check reading. `/set:push` is a one-line `git push -u` | Full pipeline incl. transcribe/extract stages before test/deploy; serialized `resource_group` | consumer (on ordinary tooling) |
| 8 | Promote → test env | Nearest thing is `milestone.py` — tags the repo, spawns a **local** dev server, emails a summary. Not an environment | Branch-as-environment `dev`→test service, `main`→prod; direction-locked prod→test refresh with outbound mail neutralised | consumer |
| 9 | Preprod | Nothing | (test env serves this role) | absent |
| 10 | Acceptance / manual sign-off | Automated tests only, pre-merge. No approval state | Release-close gate chain incl. full `@smoke+@flow` E2E and a docs-freshness gate | consumer |
| 11 | Production release | **Zero.** No versioning, changelog, rollout, rollback. Release safety is a *human checklist*, not code | Release-as-long-lived-draft YAML+notes, auto-detected migrations/env-vars/cron/API surface, 17 releases shipped | consumer |
| 12 | App operations / monitoring | Monitors **orchestration runs**, not running applications | Deploy verification correlating three systems, exit 0/1/2 = SHIPPED/FAILED/TIMEOUT, liveness proved by build-baked SHA | consumer |
| 13 | Bug intake | **Exists but is a closed internal loop.** `IssueRegistry` + ISS pipeline detect→investigate→fix→deploy; only producer is the sentinel reading its own findings | VCS-tracked `bug-imports.jsonl`, 46 bugs, stable content-derived ids, reply-to-reporter text embedded | partial / consumer |
| 14 | Incident → hotfix | **No hotfix path**, and no change type to route one to | ad-hoc (named as a gap in the author's own plan) | absent |
| 15 | ADW routing | **Partial, wrong axis.** `change_type` is build-shape (infrastructure/schema/feature/cleanup); no `bug`/`chore`/`hotfix` | — | partial |
| 16 | Multi-project | **Registry, not coordination.** `add_project`/`remove_project`/`status`; `grep portfolio\|cross_project\|global_queue` → **0 hits** | n/a | partial |
| 17 | Feedback → requirements | Closes back into **the framework** (`harvest.py:305` mines consumer fixes for framework improvements), never into a product backlog | meeting loop closes it manually | absent (product loop) |

### set-core's real boundary

**`docs/spec.md` in, merged `main` out.** One contiguous arc — decompose → implement → gate → merge — plus the supervision layer around it. Deep, real, battle-tested. Roughly one third of the candidate cycle, sitting in the middle. Everything upstream of the spec file and everything downstream of the merge commit is missing.

### Exists but dead, unwired, or lying — verified

This is the column that decides the document.

| Thing | Where | Reality |
|---|---|---|
| `run_on_integration` | `lib/set_orch/gate_runner.py:115` | Set `True` in **5 places** (`verifier.py:3977,3983`; web `project_type.py:1395,1432,1454`), **0 readers** outside two unit tests that assert the setter stores what it was given. It is exactly the per-change-vs-integration distinction a promotion pipeline needs — declared and never consumed. |
| `--accept-data-loss` | web `project_type.py:2015` | **Verified live in the working tree today.** `npx prisma db push --skip-generate --accept-data-loss` against the worktree's copied `DATABASE_URL` — which on the live consumer resolves to the production-data mirror. The `file:`-prefix guard exists **40 lines away at :2058** and was never copied. Fix is ~6 lines. |
| e2e main-baseline compare | `modules/web/.../gates.py:861` | Regex parses Playwright's default *list* reporter. The consumer switched to `--reporter json`. Match set empty → **zero failures parsed → pass**. The function's own docstring documents a *prior, identical* false-negative (ANSI escapes defeated the same anchor). Same failure class, second occurrence, same function. |
| `set-project init --force` | deploy manifest | Overwrites un-prefixed consumer files: i18n catalogs, the e2e `global-setup.ts`, 16 rules. The framework's distribution channel destroys the reset-on-start harness that the safety work depends on. |
| `Issue.source ∈ {gate, watchdog, user}` | `issues/models.py:168` | Documented taxonomy; only `sentinel` is ever constructed (`detector.py:70`). The external-report source has no producer — though `POST /api/{project}/issues` (`api/issues.py:85`) already hardcodes `source="user"`. |
| `Issue.environment` / `environment_path` | `issues/models.py:166-167` | Reads like a deployment environment. Actually holds a **registered project name and path** (`deployer.py:84-98`). A name collision that gets ~10× more expensive the moment real environments exist. |
| `compute_fingerprint()` | `issues/models.py:114` | Already sha256s a normalised summary — then the registry **discards it** for a sequential `ISS-NNN`. |
| `detect_schema_provider` | `profile_types.py:215` | Implemented in the ABC, implemented in `modules/web`, **5 unit tests**, **0 production call sites**. |
| `bin/set-router` | — | A Claude *account* manager. Not a workflow router. Name collision to resolve. |

**The measured base rate.** Twelve `ProjectType` hooks sampled for production call sites: 2 at zero (`detect_schema_provider`, `get_shell_components`), several at 1–2. Plus one dead flag with 5 writers. Plus a `project-type.yaml` override surface with 5 keys and **0 used in two months**. The author's own delegation-contract research asked, of a proposed new surface, *"will this become the 7th dead extension point?"* — he was already counting six.

**That is the number the factory question has to beat.** This repo can produce a fully-specified, fully-tested, documented extension point with zero consumers, and its test suite reports green. The test suite is complicit: it tests setters, not consumers.

---

## 3. The three designs, and what survived

Three architectures were developed independently and then adversarially reviewed. All three are summarised faithfully, including the parts that damage the position this document ends up taking.

### Design A — a separate `set-factory` repo above set-core

**Boundary principle:** the seam is not "which SDLC stage" but **state lifetime**. set-core's unit of work is a *change* — a worktree, created and destroyed, state dying with the run. A factory's unit of work is a *work item* and a *release* — permanent, spanning runs, projects, years. set-core owns everything whose state dies with the worktree; the factory owns everything that must survive it.

**Interface:** already exists and already has a second consumer (the web dashboard) — `POST /api/{project}/sentinel/start`, the state/changes/events read endpoints. Needs three additions to become a *contract*: a versioned run-result envelope, a completion callback, and `schema_version` on `state.json` and the events JSONL.

**Strongest FOR — the best sentence in the whole investigation:** the boundary is real and set-core structurally cannot cross it, and the proof is that **set-core has already tried three times and produced a half-primitive each time**. `run_on_integration` declared and never read. `Issue.source` declared with no producer. `Issue.environment` holding a project name. `milestone.py` simulating an environment with a local dev server and an email. Those are not oversights — they are what durable, multi-project concepts look like when expressed in an ephemeral single-run engine.

**Strongest AGAINST:** every verified failure to date was a missing or unwired primitive *inside the arc set-core already owns*, and adding a layer above is the one intervention that fixes none of them. The June post-mortem concluded the run collapsed on a primitive that shipped and was never called — not on insufficient planning machinery.

**Cost:** ~5–6 months to intake, ~7 with the extractions (`issues/`, harvest, milestone-promotion). Permanent tax: two repos, two release trains, one maintainer.

**Survival verdict: NEVER, as scoped.** Not "later" — the scoping is wrong in a way time does not fix. A reads its own best evidence backwards: the three half-primitives are not proof of an uncrossable boundary, they are three instances of this repo's *measured habit* of declaring extension points and never wiring them. A proposes to industrialise that habit into a second repo with its own release cadence. And A's own mitigation — *"no primitive is promoted to factory until it has fired in two projects"* — requires a second project that does not exist, while the one that does abandoned set-core mid-run and has not yet fully returned.

> **What would change this verdict:** two or more independent consumer projects, each running set-core continuously through the merge arc for ≥1 month with no fallback, needing a **shared** queue, capacity arbitration, or a joint release train. Absent multi-tenancy pressure from real second-party demand, a second repo is cost with no corresponding force.

### Design B — extend set-core, no new layer

**Two corrections that are correct and load-bearing:**

1. **set-core already has two ADWs; it just hasn't named them.** `issues/fixer.py:96` spawns `/opsx:ff → apply → verify → archive` directly in the target project, **bypassing decompose, the planner, the dispatcher and the merge queue entirely** — with its own approval policy, its own state machine, and `max_parallel_fixes: int = 1  # Hard rule`. ADW differentiation is naming plus two additions, not greenfield.
2. **`change_type` is the wrong home for chore/bug/hotfix.** It is *build-shape*, load-bearing in four subsystems including eight LLM prompt sites, and "where does a hotfix sit in phase 1..N" has no answer. The answer is an orthogonal `work_class` axis with a ~30-line `WORK_CLASS_OVERLAY` inserted into the existing 7-step gate-resolution chain — composing with all six `change_type` values without touching any of them. Note it pins `hotfix → review: "run"`: the one gate that may never be skipped.

**Also proposes:** consuming `run_on_integration` to make `_run_integration_gates` registry-driven; a `phase="promote:<env>"` value; deploy verification as a first-class primitive with `detect_deploy_command`/`deploy_health_url`/`parse_build_sha` hooks. **Explicitly refuses** the meetings pipeline.

**Strongest FOR:** the gaps sit on abstractions set-core already owns, several already declared in its own code. `GateDefinition.phase` already spells `pre-merge|post-merge`. `Issue.source` already spells `user`. The issues API already hardcodes `source="user"`. `compute_fingerprint` already computes stable ids. `milestone.py` already does tag→env→verify→notify. Extension here is *finishing sentences set-core started*. A separate repo would have to reach *through* every one of them and version each reach across two release cadences.

**Strongest AGAINST — which B itself states and cannot dissolve:** its first move is to widen an arc that is not closed. B's P2 is a rewrite of `merger.py:1686 _run_integration_gates`, the most load-bearing function in the repo, carrying ~15 incident-driven special cases (e2e redispatch, coverage redispatch, identical-output hash detection, `.env` loading, `integration_pre_build`). Dropping one regresses **silently** — and silent gate regression is this project's signature failure mode, currently with three live instances.

**Also honest about two structural strains:** (a) deployment varies along *where does it run* (Railway/Vercel/k8s/VM), which is a different axis from the plugin model's *what kind of code is this* — two Next.js projects share `WebProjectType` and share nothing about promotion; (b) **state lifetime breaks outright** — a backlog, a release train, an environment ledger and a production issue history are long-lived, and every subsystem under `lib/set_orch/` is run-scoped.

**Survival verdict: DEFER, with the ordering endorsed.** B is the most technically credible of the three and its diagnosis is right. It is deferred because it widens an unclosed arc, and because B's own risk 3 is the base-rate argument in B's voice: *"the router gets built and has nothing distinct to route to… shipping `work_class` as a taxonomy with near-zero behavioural delta is a false gate in the consumer's exact sense, and this repo already has three."*

> **Trigger:** Phase 0′ + 0a + 0b shipped, **and** one consumer runs a full week on set-core gates with zero fallback, **and** `run_on_integration` consumed *additively* (registry gates run after the hardcoded ladder, both verdicts logged) across two E2E runs showing identical verdicts. Then B's P1 is the correct next step. And B's own recommended ordering stands: **build the hotfix ADW first; add the router only once two provably different pipelines exist to choose between.**

### Design C — ports, not layers

**Rule:** set-core owns a stage iff it is (a) repo-local, (b) reproducible from a git ref, and (c) has a deterministic pass/fail. Requirements elicitation fails (a) and (c). Deployment fails (a) and (b). CI fails (a). A bug register *as a file in the repo* passes all three — which is precisely why the consumer put its register in a JSONL file rather than the app's database: the gates that read it run at pre-push and release-close, **where no database exists**.

**Four components:** a typed intake port (a file contract set-core validates and reads but **never produces**); a deterministic `work_kind` router on a second axis; an outcome port — `.set/factory.yaml` with a closed verb set (`promote`, `verify_deploy`, `release_close`, `notify_reporter`), each mapping to a project command with a fixed exit-code contract, plus wiring `run_on_integration`; and a **baseline-ratcheted gate type** (gate + VCS-tracked baseline file + the invariant *the baseline may only shrink*).

**Strongest FOR:** every increment is independently valuable even if the factory is never built. And C is the only option consistent with all three evidence sources simultaneously — the sources' "start simple, separate code from agents, the router can be deterministic"; the consumer's ~20 primitives that each exist *because a specific incident happened* and therefore could not have been designed in advance; and the post-mortem's missing-primitive verdict.

**Strongest AGAINST:** the boundary may not hold and C has no plan for the day it breaks. Every stage C pushes to adapters is long-lived and multi-project, while set-core's state model is per-run. C papers over that with "it's just a file in the repo," which works for one project and has no owner for state spanning projects.

**Survival verdict: DEFER — and unbundle it.** Two things damage C badly on inspection. First, **C's Phase 0 is not C's work.** The data-loss guard, the e2e reporter fix and `init --force` prefix safety are `final-plan-2026-07-19.md` Phases 0′/0a/0b **verbatim** — already planned, already sequenced, already owed regardless. Strip them out and C is 4–5 weeks of new ports over an engine whose four verified defects are still live. Second, C's intake port is *"set-core never produces these records"* — an extension point that is **dead by construction** until someone external writes an adapter. That is the literal definition of the thing this repo has built six of. C's own risk-1 mitigation requires shipping a dead-extension-point detector *in the same PR as the port*. A design that needs that is telling you its base rate.

**But C's exclusion argument is the strongest single conclusion in the investigation, and it survives fully** — see §5.

---

## 4. The evidence that decided it

Four independent lines converge. None of them is about architectural taste.

**(1) The repeat.** The June post-mortem opened with the consumer team's hypothesis — *"we did not know what LEVEL of specification set-core needs"* — and demolished it: the spec was 5,900 lines, 338 KB, 47 requirements, 212 acceptance criteria. *"The spec-level hypothesis is wrong on the premise."* The actual cause: ~36 smoke tests already failing on `main`, and the integration e2e gate never applying the main-baseline compare. 20 of 22 redispatch events carried `reason=integration_e2e_failed`; ~45% of token spend went to gate churn caused by an **uncalled primitive**. Today's live analogues are the same class three more times: a flag with 5 writers and 0 readers; a gate reading the wrong surface and seeing nothing wrong; a guard that exists 40 lines from where it is needed.

**(2) The base rate.** 2/12 sampled hooks dead, one dead flag, a 5-key config surface at 0% adoption over two months, and the author's own count of six dead extension points. **All three designs named the dead-extension-point risk as a top-3 risk.** When three adversarially-separated designs converge on the same top risk, that is not a risk to mitigate — it is the finding.

**(3) The trust premise has never been measured.** Every component of the ambition is a levered bet on one quantity: *does a green set-core verdict mean the code is good?* Auto-implement bets on it once. Auto-promote bets production on it. Multi-project bets it N times with no added reviewer. The only two data points that exist are both false-greens: a `rules` gate configured `"warn"` in 5 of 6 change types and `"skip"` in the 6th — **it can never block anything** (`gate_profiles.py:71,80,89,98,107,116`) — and an e2e comparator returning zero failures under the reporter the live consumer runs. Set-core's gate false-negative rate is unknown.

**(4) The consumer's own automation already falsifies the meetings claim.** 37 of 65 decision files carry `backfill: "2026-07-18"` with `date:` fields spanning 2026-06-04 to 2026-06-30 — a 3-to-7 week lag, all landed in one commit whose message translates as *"backfill of 37 **missed** decisions."* Capture had the transcripts the whole time; **capture was never the bottleneck, interpretation was, and interpretation is the human.** Agenda generation is not automated at all (grep across scripts and commands: zero hits) because the agendas contain live customer-relationship risk judgment. And when the automated capture failed once — a session died and lost the first ~42 minutes — the recorded consequences were: a note that stated **the opposite** of the actual pricing decision, which **shipped to production**; and a superseded requirement that governed the build for weeks. Detection was luck (a nightly sync surfaced the real transcript that evening). **A factory cannot gate on a stage whose failure signal is "someone happened to find the recording later."**

**(5) The commit log, which is the uncomfortable one.** Five consecutive commits since 2026-07-14 (`9d464884`, `070dbfc1`, `50f82f0c`, `18562065`, `afb3be75`), all documentation, zero lines of code. The last commit touching the web `project_type.py` was 2026-07-09. `final-plan-2026-07-19.md` §6, committed at 00:26 this morning, ends: *"Ship the 6-line SKIP guard at `project_type.py:2015` … **today**."* Eleven hours later the next commit was another research document, and a three-design factory investigation was opened. The fair version of this timeline is worse than the unfair one: the data-loss path was **discovered today**, so this is not weeks of neglect — it is *urgency being converted into documentation within hours of discovery*. All three factory designs reproduce that Phase 0 faithfully. **None of them shipped it.** When three designs agree on step one, step one is not a design question.

---

## 5. The recommendation

**Do not build a `set-factory`.** Not as a repo (Design A: never, as scoped), and not yet as an extension (Designs B and C: defer). The full dev+ops cycle should stay **distributed**, not consolidated into either place:

- **set-core keeps its arc** — decompose → implement → gate → merge — and *closes* it before widening it.
- **The consumer keeps CI, promotion, release and deploy** on ordinary tooling, because that is where they already work, and work better than set-core's equivalents. A factory that owns CI, promotion, release management and ticketing is reimplementing a CI platform, a PaaS, and an issue tracker. The consumer's deploy verification — the single genuinely-missing-everywhere primitive — is a ~200-line shell script with exit codes 0/1/2, not a platform.
- **The seam between them becomes a declared contract**, not a coincidence — which is exactly what `final-plan`'s Phase 1 and the consumer-readiness `set/contract.yaml` work already specify. That work is the factory ambition's honest first instalment, and it is already planned.

### What should never be built into the framework

**The meetings → requirements pipeline.** Not deferred — excluded, permanently. Three independent reasons, and it is the largest single component of the question as asked:

1. **No prior art supports it.** The sources' factory begins at a ticket that already exists. Any case for this component cites nothing.
2. **It is transport plus governance, not engine.** The consumer's version is six edge workers, a transcription vendor, a video toolchain, a chat integration, a CI transcribe stage, and a four-tier human approval ladder encoded in prose. The reusable residue is **two ideas** — the three-layer `inputs → converted → knowledge` contract, and the **knowledge→spec firewall** (a spec may read only the interpreted layer, never raw input). Both are *rules text*, deployable at zero engine cost.
3. **The measured failure mode is a wrong requirement reaching production with accidental detection.** The consumer's own `supersedes:` chaining and `backfill:` field exist *because* the automation is known to miss; they are manual reconciliation instruments, correctly built. Automating the interpretation step is not an engineering gap — it is the part where the human is the mechanism.

A framework that ingests recordings and stakeholder identities also inherits confidentiality obligations a public repo cannot discharge.

### Also not built now

**Cross-project portfolio scheduling.** Registry-level multi-project already works. What breaks at N is not scheduling: the one genuinely contended resource is API quota, and `bin/set-router`'s own header states that automatic rotation to circumvent rate limits violates the provider's ToS — a legal fence, not a technical one. A scheduler cannot solve it; it can only queue behind it. The second contended resource is human review bandwidth, which scales at zero. **The binding constraint is human review bandwidth, and no scheduler creates more of it.** Note also the awkward fact underneath the ambition: set-core's own E2E runners default to `max_parallel=1` on purpose — the proposal is N projects × continuous parallel work on an engine whose defaults are serialised because parallelism did not work.

### The trigger for revisiting

Revisit the factory question when **all** of the following hold — not any one of them:

1. `final-plan` Phases 0′, 0a, 0b are shipped and in a consumer's hands.
2. One consumer has run a full week on set-core gates with **zero** fallback to plain OpenSpec.
3. The gate mutation test (§7) returns **≥90%** catch rate.
4. `run_on_integration` has been consumed additively across two E2E runs with identical verdicts between the old ladder and the registry-driven one.

And revisit the *layer* question (A vs B) only if C's own falsifier fires: within 6 months, either two or more projects need a shared queue / capacity arbitration / joint release train, or the adapter verb set grows past ~10. Until then, the portfolio dimension is speculative.

---

## 6. What to do, in what order

### Now — the debt, which is not a factory phase and must stop being counted as one

These are `final-plan-2026-07-19.md` Phases 0′/0a/0b and consumer-readiness Blockers #1–#3. They are owed regardless of every question in this document.

| # | Item | Where | Size |
|---|---|---|---|
| **0′** | Literal SKIP guard on the destructive prisma call | web `project_type.py:2015` (copy the shape of the guard at `:2058`) | **~6 lines, today** |
| **0a** | `protected: true` flags in the web deploy manifest for `messages/*`, `tests/e2e/global-setup.ts`, `.gitignore`, the pre-commit hook, `project-knowledge.yaml`; prefix-or-protect the 23 `rules/` entries; fix the `code-reviewer.md` basename collision | deploy manifest | ~1 day |
| **0a′** | `--no-verify` on automated worktree commits/pushes (consumer-readiness Blocker #2 — otherwise re-armed hooks stall the run in a retry storm) | dispatcher | small |
| **0b** | e2e gate reads a machine-readable result file keyed on `(file, title)` instead of scraping the list reporter | `gates.py:861` | ~1–2 days |
| **0c** | "Gate skipped" must **log why**. Today it skips silently — that is how the false-green hid | gate runner | trivial, ship with 0′ |

**Nothing else starts until 0′ is committed.** Not because six lines take a week, but because the measured pattern of this repo is that Phase 0 gets deferred for the more interesting Phase 2 — which is *literally what happened to `run_on_integration`*, and what Design A predicted about itself.

### Next — cheap to design for now, expensive to retrofit later

This is the genuine steelman of the whole factory ambition, and it is small. The test is **not** "is it valuable" — most factory capability is valuable and retrofittable at roughly constant cost. The test is **"does the retrofit cost grow with time?"** Three things pass:

1. **The identity thread.** Stable, content-derived work-item ids threaded change → branch → commit trailer → gate outcome → release. `compute_fingerprint()` at `issues/models.py:114` **already computes it and the registry throws it away** for a sequential `ISS-NNN`. Promoting it to the durable external id is a small change inside code set-core already owns. It passes the test because **you cannot back-fill an id onto a commit already written** — every day without it, the corpus that can never be threaded grows. The consumer measured exactly this: 93% of `fix:` commits leave no trace in spec or knowledge, and they run three parallel bug registers with one-way sync. A bug register, a regression ratchet, a release manifest and a reply-to-reporter gate all key on this one decision. **It is not factory construction; it is a naming decision, and it costs nothing if the factory is never built.**
2. **The versioning seam.** `schema_version` on `state.json` and the events JSONL. Its absence is *how the e2e baseline broke*: the reporter format changed underneath a regex, the regex read zero failures, nothing errored. A version field turns silent drift into a loud failure. Near-zero code, and unversionable retroactively for data already written.
3. **The naming collision.** Rename `Issue.environment` / `environment_path` → `project` / `project_path` (`deployer.py:84-98` proves what they hold). One line each now; ~10× more expensive after any real environment concept lands. Same for the `bin/set-router` name.

Also cheap now, zero engine cost, and the correct home for the meetings work: **ship the `inputs → converted → knowledge` contract and the knowledge→spec firewall as rules text** deployed via `set-project init`. That captures the entire reusable residue of the intake ambition.

### Then — the contract, which is the factory ambition's honest first instalment

`final-plan` Phase 1 (`lib/set_orch/contract.py` + `set/contract.yaml`, resolution order contract > directives > `profile.detect_*` > None, with **None ⇒ skip AND log why**) and Phase 2 (worktree DB isolation through a profile/contract hook, never a Layer-1 hardcoded suffix), paired with the consumer-side inputs already listed in consumer-readiness §5. This is delegation, not expansion: set-core stops making concrete decisions it cannot safely make — *which DB is disposable, whether a green e2e run passed* — and reads them from a declaration the project owns. Those two wrong decisions are precisely what produced the data-loss path and the false-green.

### After the trigger fires — and only then

In this order, each gated on the previous:

1. **Consume `run_on_integration` additively** — registry-driven integration gates run *after* the hardcoded ladder, both verdicts logged, ladder collapsed only when two E2E runs agree. This retires a dead flag by consuming it rather than deleting it, and it is the prerequisite for anything downstream.
2. **The baseline-ratcheted gate type.** A gate + a VCS-tracked baseline file + the invariant *the baseline may only shrink*. The consumer arrived at this independently four times. It is the only mechanism that lets you introduce a gate into a codebase that already violates it, and set-core has nothing like it. First consumer: every FIXED work item must be referenced by id in a test file — which is what the identity thread was built for.
3. **The hotfix ADW — first, and alone.** Not the router. Skip decompose, single change, surgical prompt, **mandatory human approval before merge**, gates narrowed to build+smoke with `review: "run"` pinned. This is the one differentiated pipeline with a real, named, currently-ad-hoc gap. `fixer.py:96` proves the second-ADW pattern already works in this codebase.
4. **`work_class` + the gate overlay + a deterministic router** — only once two provably different pipelines exist to choose between. Building the taxonomy first produces a false gate, and this repo already has three.

**Never:** meetings→requirements as engine code; deployment execution; a promotion state machine owned by set-core; portfolio scheduling; ZTE.

---

## 7. The unproven assumptions

| # | Assumption | Cheapest experiment | Decision rule |
|---|---|---|---|
| **1** | **A green set-core gate verdict means the code is good.** *The single biggest one.* Every component of the ambition is levered on it: auto-implement bets once, auto-promote bets production, multi-project bets N times with no added reviewer. **Never measured.** The only two data points are both false-greens. | **Gate mutation test — one day, no new framework code.** Take one recently merged consumer change. Generate ~12 mutants, one per defect class the gates claim to catch: deleted null check, flipped boundary comparison, dropped `await`, schema change without migration, hardcoded secret, broken e2e assertion, a rule violation, a PII log, a removed auth check. Run the **full** chain (per-change + merge-queue integration gates) against each. Count catches and list every gate that passed a known-bad input. | **<90% → no promotion capability may be built under any architecture**, and the answer to the whole question becomes "fix the middle." **≥90% →** the premise survives its first test and the argument moves to which stages are worth owning vs delegating. |
| **1a** | *(20-minute pre-check, may settle #1 before the full run)* The e2e gate is lying **today**. | Re-run the last archived orchestration's e2e gate twice — once `--reporter=list`, once `--reporter=json` — and diff the parsed failure counts. | If they differ, one production gate is confirmed lying now, and every downstream claim rests on it. |
| **2** | **The factory layer would be used, not become the 7th dead extension point.** Base rate says 17% of sampled hooks are dead, plus a flag at 5 writers/0 readers, plus a config surface at 0% over two months. | Ship the identity thread and the contract reader, then measure adoption at 60 days: is the fingerprint id actually threaded into commit trailers? Does any project author a `contract.yaml`? | Zero adoption of the *cheapest* surface after 60 days ⇒ the base rate holds and no larger surface should be built. |
| **3** | **set-core is trusted enough to build on.** The consumer started on set-core, fell back to plain OpenSpec mid-project, and is now trying to return. | One consumer runs a full week on set-core gates with zero fallback, post-0′/0a/0b. | Any fallback event ⇒ the arc is still not closed; stop and fix what caused it. |
| **4** | **Requirements can be produced from meetings by machine.** | **Already falsified** by the consumer's own tree: 37 of 65 decisions backfilled 3–7 weeks late in one human batch; agenda generation not automated at all; one capture failure shipped a wrong requirement to production with accidental detection. | No experiment needed. Do not build it. |
| **5** | **Portfolio scheduling is the bottleneck at N projects.** | **Already answered:** the contended resources are API quota (ToS-fenced, `bin/set-router` is manual for legal reasons) and human review bandwidth (scales at zero). | Neither is a scheduling problem. Do not build a scheduler. |
| **6** | **Deployment fits the plugin model.** Two projects can share a project-type plugin and share nothing about promotion. | Sketch `detect_deploy_command()` for two hypothetical targets on the same project type. | If it degrades to "read a command from config," the ABC hook is theatre and deployment needs a *separate* extension axis — which should be said out loud, not hidden inside `ProjectType`. |
| **7** | **The consumer's ~20 primitives generalise.** Each exists because a specific incident happened — a stuck migration, a release-manifest typo stalling a live deploy twice, twelve fixed bugs with zero regression tests. Generalised before a second project has had those incidents, they produce gates that are wrong in the general case. | Promote no primitive until it has fired in **two** projects. | There is currently one project. |

### Where this document is uncertain

Two places, honestly.

**Design A's boundary argument may be right.** State lifetime *is* a real architectural seam. `ServiceManager` is a registry rather than a coordinator plausibly because set-core has no vocabulary for state outliving a worktree — not because nobody got to it. If the portfolio dimension ever becomes real, this document's answer will look like it deferred a structural problem into config sprawl. The counter is that the evidence for the boundary is identical to the evidence for the dead-extension-point habit, and the two readings are not currently distinguishable — which is itself a reason to wait for evidence that *does* distinguish them.

**The identity-thread recommendation is a bet that costs a little now to save a lot later, and that bet could be wrong.** If the factory is never built and traceability never matters, it is a small amount of wasted work. It is recommended anyway because it is the only item in the entire ambition whose retrofit cost is monotonically increasing.

---

## 8. In one line

The author's own research already concluded the software-factory frame is satisfied by the set-core ↔ app split and deferred the only genuinely missing piece — a between-ADW router — as *"the existing router could grow here"*; the post-mortem concluded June collapsed on a missing primitive, not missing planning machinery; and since that conclusion this repo has produced five research documents and zero lines of code while a six-line guard stands between an orchestration run and a production-data mirror — **so the answer is not a `set-factory` in any design, but the six lines, the identity thread, and the contract, in that order, and the meetings pipeline never.**