# Consumer and orchestration Claude — the two branches have separated

**Source data: 5 micro-web E2E runs on the `set-core` framework, May 1–2, 2026. All on the same `spec.md` (sha=ef1006c4, 198 lines).**

On May 2 at 11:04 AM (commit `db82ebb0`) we re-mapped the `opus` model alias in the `set-core` repo from `claude-opus-4-7` to `claude-opus-4-6`, because of how the 4.7 was behaving. Alongside the alias flip we purged hardcoded `"opus"` fallbacks from 40+ call sites and introduced a 13-leaf-role, 5-tier resolver chain.

This document records **only what the run data actually shows.** Every number is backed by an `orchestration-state.json` and journal source, and there is an explicit caveats section at the end on what the data does *not* support.

---

## TL;DR

Same 198-line spec:

- **With the 4.7 default model (opus alias→4-7) the planner decomposed it into 12 chunks**, and the full run cost **1.40 million output tokens**.
- **With the 4.6 default the planner decomposed the same spec into 5 chunks**, and the full run cost **642 thousand output tokens**.

Same output. **2.17× more token spend on the 4.7 side.**

The difference is not per-token efficiency (per-chunk median token count is actually *higher* on the 4.6 side, 136k vs 76k). The difference is the **creativity of the planner LLM's decision-making**: the 4.7 cuts the work into finer pieces than necessary, producing 12 dispatch points, 12 verify-gate cycles, 12 merge surfaces — instead of 5.

Within that, **407,505 tokens (29.2% of the 4.7 run) went to changes nobody asked for**: the 4.7 planner generated 4 standalone test/E2E change records on the side, while E2E testing is the responsibility of the `set-core` verify gates (and the spec itself prescribed the tests at feature level). The 4.6 planner did not do this once on the same spec.

The change-level "wandering" is tangible: one change in the 4.7 run (`blog-list-with-filter`) **burned 292,086 tokens**, and along the way broke the spec test of *another* already-merged change it had no business touching. The 4.6 run's analogous, **larger**-scope change (`blog-pages` — blog list + detail combined) closed in 136,158 tokens, with no retries, on a direct `planning → merging` path.

---

## The runs — natural A/B from commit timing

| Run ID | Started | Default model | Spec sha | Outcome |
|---|---|---|---|---|
| `micro-web-run-20260501-1805` | 2026-05-01 18:05 | **4.7** (opus→4-7) | ef1006c4 | 12/12 merged |
| `micro-web-run-20260502-0245` | 2026-05-02 02:45 | 4.7 | ef1006c4 | 6/9 merged, 3 paused/pending |
| `micro-web-run-20260502-1104` | 2026-05-02 11:04 | **4.6** (post-rollback) | ef1006c4 | 5/5 merged, 0 paused |
| `micro-web-run-20260502-1326` | 2026-05-02 13:26 | 4.6 | ef1006c4 | 3/6 merged, 3 paused/pending |
| `micro-web-run-20260502-1545` | 2026-05-02 15:45 | 4.6 | ef1006c4 | (partial run) |

The spec file is SHA-256-verified identical across all 5 runs. The only variable is the defaults (the opus alias mapping).

The two "clean" runs I'll put side by side:
- **4.7 reference**: `0501-1805` — full 12-change spec, all merged, well-instrumented
- **4.6 reference**: `0502-1104` — full 5-change decompose, all merged, well-instrumented

The other runs were either cut short or had manual intervention.

---

## Decomposition divergence — same spec, two different plans

The `set-core` planner phase uses an LLM for spec → change decomposition (`decompose_brief`, `decompose_domain`, `decompose_merge` roles). On the same 198-line spec:

### 4.7 planner output (run 0501-1805): **12 leaf changes**

| # | Name | Complexity | Model |
|---|---|---|---|
| 1 | foundational-scaffold-and-shell | M | sonnet |
| 2 | test-infrastructure-setup | S | sonnet |
| 3 | site-header-and-mobile-nav | M | opus |
| 4 | home-page-and-newsletter-sheet | S | opus |
| 5 | about-page | S | opus |
| 6 | blog-list-with-filter | M | opus |
| 7 | contact-page-and-wizard | M | opus |
| 8 | blog-detail-with-progress-and-reactions | M | opus |
| 9 | command-palette | M | opus |
| 10 | validation-and-contact-wizard-tests | S | opus |
| 11 | pages-smoke-and-blog-filter-e2e | S | opus |
| 12 | cmdk-and-mobile-nav-e2e | S | opus |

### 4.6 planner output (run 0502-1104): **5 leaf changes**

| # | Name | Complexity | Model |
|---|---|---|---|
| 1 | foundation-navigation | M | opus |
| 2 | home-about-pages | M | opus |
| 3 | blog-pages | M | opus |
| 4 | contact-wizard | M | opus |
| 5 | blog-reactions-and-acceptance | S | opus |

### Observation

The 4.7 planner created standalone changes **just for the E2E specs** (`pages-smoke-and-blog-filter-e2e`, `cmdk-and-mobile-nav-e2e`, `validation-and-contact-wizard-tests`) — meaning 3 changes worked on what was, on the 4.6 side, just the `Ship E2E tests at e2e/...` section of each feature change. The 4.7 also fragmented navigation (header + mobile-nav, command-palette, cmdk-e2e — three chunks for what the 4.6 covered with a single one: `foundation-navigation`).

This is not a wrong decision in the classical sense. In a single-agent vibe-coding context, finer chunking can even be an advantage ("smaller context window, more focused agent"). **But in multi-agent orchestration every chunk boundary is a failure surface**: dispatch, verify-gate sequence, merge conflict, sibling-spec drift. The 4.7 builds 12 such surfaces against the 4.6's 5.

---

## Two concrete wandering patterns

The spec decomposition really did come out "more creative" on 4.7, in two distinct, clearly visible ways.

### 1. Standalone test and E2E change records — that nobody asked for

The `set-core` framework handles E2E and unit tests at the **gate level**: every change's verify pipeline includes `test`, `e2e`, `e2e_coverage`, `lint`, `build`, `design-fidelity`, and `scope_check` gates. If a change ships feature code but forgets the tests, the gate flags it — so there is no need for an LLM to create a separate change record for "testing tasks."

The 4.7 planner did this anyway. Of the 12 changes in the `0501-1805` run, **4 are test/infra-only**:

| Change record | Type | Tokens | Counterpart on 4.6 side? |
|---|---|---:|---|
| `test-infrastructure-setup` | infrastructure | 34,462 | – (configured by feature changes) |
| `validation-and-contact-wizard-tests` | feature | 115,559 | – (part of `contact-wizard` feature) |
| `pages-smoke-and-blog-filter-e2e` | feature | 59,268 | – (part of `blog-pages`) |
| `cmdk-and-mobile-nav-e2e` | feature | 198,216 | – (part of `foundation-navigation`) |
| **Total** | | **407,505** | **0 standalone test changes** |

**The full 4.7 run cost 1,396,841 tokens → of which 407,505 (29.2%) went to changes the 4.6 planner did not create at all.** The spec states REQ-TEST-001..006 requirements — the 4.6 folded these into the feature changes' scope ("Ship E2E tests at e2e/...spec.ts"), which is exactly the form `set-core`'s testing-conventions.md prescribes. The 4.7 instead manufactured separate orchestration units around them, **without the spec asking for it**.

The 4.7 `0245` run had 1 such change out of 9 (`test-infrastructure-setup`). The 4.6 `1104` and `1326` runs had **0 of these**. So the pattern isn't constant on 4.7, but it is asymmetric: it does not occur on the 4.6 side, it does on the 4.7 side.

### 2. v0.app design drift (observed, not measured)

The micro-web stack is built against a `v0-export/` reference (components generated in v0.app). `set-core` runs a `design-fidelity` gate between planner and verify-gate, which reports token mismatches as `[WARNING]` and critical contract drift as `[CRITICAL]`.

**In these runs that gate output was a stub** (32-character fixed string across all 5 runs) — meaning I cannot quantify v0.app drift frequency from this dataset. Anecdotally (from the contents of the worktrees, and from the fact that the `design-pipeline.md` and `design-bridge.md` rules address exactly this), the 4.7 was more prone to improvising component variants **not present** in the v0-export (extra `Card` layering, non-token-based spacing), but I cannot back the precise volume of this from the run metadata above. **Use this in the article as a qualitative observation; do not attach numbers to it.**

---

## Token spend, on the same spec

The `tokens_used` field is the per-change cumulative token counter (input + output + cache + retries all inclusive). Computed over merged changes:

| Metric | 4.7 (1805) | 4.6 (1104) | Ratio |
|---|---:|---:|---:|
| Changes (all merged) | 12 | 5 | — |
| **Sum output tokens** | **1,394,032** | **642,603** | **2.17×** |
| Sum input tokens | 205,363,639 | 115,059,327 | 1.79× |
| Sum cache-read tokens | 205,360,830 | 115,057,537 | 1.79× |
| Sum cache-create tokens | 11,448,986 | 5,143,953 | 2.23× |
| Cache-hit ratio | 48.64% | 48.91% | ≈ |

**Output tokens are the main billable line item** on the Claude API. Here it's a **2.17× difference** for the same output. Cache-hit ratio is essentially identical (~49%) — meaning prompt-cache efficiency did not regress; **the agents simply did more total work**.

### Per-change median

| Metric | 4.7 (1805) | 4.6 (1104) |
|---|---:|---:|
| Median tokens/change | 76,550 | 136,158 |
| Mean tokens/change | 116,403 | 128,879 |
| Max tokens/change | **292,086** (blog-list-with-filter) | 185,226 (contact-wizard) |
| Mean duration / change | 22.5 min | 21.9 min |

Per-chunk median is *higher* on the **4.6** side — because fewer, larger chunks. Per-spec total is *higher* on the **4.7** side. The two numbers together tell the story: **the 4.7 makes many small chunks, the 4.6 makes few big ones, and "many small chunks × per-chunk overhead" is what makes it 2× more expensive.**

---

## Stuck-loop, paused, verify-retry — run stability

| Metric | 4.7-1805 | 4.7-0245 | 4.6-1104 | 4.6-1326 |
|---|---:|---:|---:|---:|
| `stuck_loop_count` (sum) | **1** | 0 | 0 | 0 |
| Paused/pending changes | 0 | **3 / 9** | **0** | 3 / 6 |
| Changes with verify-retry | **3 / 12** | 2 / 6 | 1 / 5 | 2 / 3 |
| Build-fix attempts | 1 | 0 | 0 | 0 |

The 4.7 `1805` run merged 12/12 — but **had 1 stuck-loop along the way** and 3 different changes needed verify-retry. The 4.7 `0245` run only managed to close 6 of its 9 changes on its own; **3 stayed in paused/pending** state (manual intervention or timeout).

The 4.6 `1104` run **merged all 5 changes, zero paused, zero stuck**. The `foundation-navigation` change took 4 verify-retries — but it eventually passed. This is the "concentrated retry" pattern: **stubborn at one site, but deterministic**, contrasted with the 4.7 "spread retry" (1 retry each at 3 different sites).

---

## The concrete story — `blog-list-with-filter` (4.7) vs `blog-pages` (4.6)

The most expensive change in the 4.7 `1805` run: `blog-list-with-filter`. **It used 292,086 tokens**, run time ~44 minutes (19:12 → 19:56). Journal file `blog-list-with-filter.jsonl`, 64 events.

### 4.7 step transitions

```
2026-05-01 19:12:18  → planning
2026-05-01 19:23:11  → fixing       ← stuck here
2026-05-01 19:56:07  → merging
2026-05-01 19:56:08  → archiving
2026-05-01 19:56:09  → done
```

The `fixing` step generated **two retry_context messages**. The first:

> *E2E gate failed with exit_code=1 but Playwright did not emit a failure list. This usually means the suite crashed before completing — check the worktree for stack traces, OOM kills, webServer startup errors...*

The second — the critical one:

> *Integration smoke gate FAILED: 1 of 2 inherited sibling spec(s) failed. (...) Failing spec files: tests/e2e/foundational-scaffold-and-shell.spec.ts*

That is: the `blog-list-with-filter` agent did something that **broke the spec test of the `foundational-scaffold-and-shell` change** — another change that had already been merged into `main`. The test output: `ERR_CONNECTION_REFUSED at http://localhost:4093/` and `ENOENT: no such file or directory, mkdir '...wt-blog-list-with-filter/.next'`. The agent had touched something in the build process / scaffold contract that it had no business touching.

This is the journal-line-level fingerprint of "scope wandering."

### 4.6 equivalent

The 4.6 `1104` run's `blog-pages` change covers the blog list **and** the blog detail (on the 4.7 side these were 2 separate changes). **It used 136,158 tokens**, run time ~23 minutes (11:50 → 12:13). Journal: 32 events (half of the 4.7 side's 64).

```
2026-05-02 11:50:16  → planning
2026-05-02 12:13:25  → merging
2026-05-02 12:13:26  → archiving
2026-05-02 12:13:27  → done
```

**No `fixing` step. No retry_context. `verify_retry_count=0`.** Straight from planning to merging.

### The parallel

| | 4.7 `blog-list-with-filter` | 4.6 `blog-pages` |
|---|---|---|
| Scope | blog list + filter only | blog list + filter **+** blog detail |
| Tokens | **292,086** | **136,158** |
| Time | ~44 min | ~23 min |
| Journal events | 64 | 32 |
| `fixing` step | yes, twice | no |
| Broke a sibling spec | yes (foundational scaffold) | no |

The 4.7 did the **smaller** scope, used **2.15× more tokens** doing it, and **broke another already-merged change in the process.** This is the concrete shape of "too creative, wanders off."

---

## The split shows in the architecture too — three commits

The model rollback wasn't a default flip. Three commits, ~2.5 hours, to turn "model alias" from a single string into a 5-tier resolver chain, per role. All on `set-core`'s `main` branch, May 2, 2026.

### 1. `8cdcbd9f` — `feat(model-config): unified models block + opus-4-6 default + foundational→opus` (09:45)

`lib/set_orch/config.py` schema extended with a top-level `models:` directive block containing **13 leaf roles**:

```
agent, agent_small, digest,
decompose_brief, decompose_domain, decompose_merge,
review, review_escalation,
spec_verify, spec_verify_escalation,
classifier, supervisor, canary
```

…and a 4-key trigger sub-dict (`integration_failed`, `non_periodic_checkpoint`, `terminal_state`, `default`).

New module: `lib/set_orch/model_config.py`, with a `resolve_model(role, *, project_dir, cli_override)` function that implements a **5-tier chain**:

```
1. CLI override                         (--model … flag)
2. SET_ORCH_MODEL_<ROLE>                env var
3. orchestration.yaml → models.<role>   per-project config
4. profile.model_for(role)              per-stack plugin override
5. DIRECTIVE_DEFAULTS                   framework-level fallback
```

Trigger sub-roles are addressable via dotted paths: `trigger.integration_failed` → `SET_ORCH_MODEL_TRIGGER_INTEGRATION_FAILED`. Any layer with an unknown role or an invalid model name → `ValueError`, fail-loud.

Plus a `PRESETS` dict for the `--model-profile` shortcut: `default`, `all-opus-4-6`, `all-opus-4-7`, `cost-optimized`.

### 2. `db82ebb0` — `fix(model-config): purge hardcoded model fallbacks; opus alias → 4-6` (11:04)

The root-cause fix. The previous run (the 0245 micro-web run) demonstrated that Phase B was not actually taking effect: agents were still running on `claude-opus-4-7`, despite the new default. Two reasons:

1. `_MODEL_MAP["opus"] = claude-opus-4-7` (the latest family alias). The "default" role's new value was `opus`, which resolved back to 4-7.
2. **40+ call sites had hardcoded `or "opus"` fallbacks** — `cli.py`, `builder.py`, `planner.py`, `investigator.py`, `category_resolver.py`, `dispatcher.sh`, `digest.sh`, etc. These **bypassed** the new resolver.

The fix:

```python
# subprocess_utils.py + bin/set-common.sh (kept in sync)
_MODEL_MAP["opus"] = "claude-opus-4-6"   # was: claude-opus-4-7
```

…and every hardcoded fallback rewritten to `resolve_model("<role>")`.

### 3. `fd9583be` — `fix(model-config): legacy directive defaults shadowed unified models block` (12:10)

Another bug. `DIRECTIVE_DEFAULTS["review_model"] = "opus"`, a legacy default, **leaked through** into project state (`state.directives`), and `verifier.py:_execute_review_gate` read that *before* the result of `resolve_model("review")`. The verify-review gate was running on `opus` the whole time, even though we'd configured it to `sonnet`. **Surfaced via the Tokens UI panel** showing the review-call actually ran on `opus`.

Plus: the `LLM_CALL` event used to log with the alias (`"opus"`), now it logs with the resolved full ID (`claude-opus-4-6`). This is a self-observability fix — until now your own UI was lying to you about which model ran.

### Significance of the three commits

In a consumer-model single-shot context, "model name" = string. In an orchestration-model context, **model name = 13 roles × 5-tier resolution priority × explicit fail-loud invalid-input handling**. The two branches are no longer solving the same problem — and the shape of the codebase is what shows it.

---

## What the data does not say (caveats)

An honest list of what shouldn't be inferred from these numbers:

1. **There is no 1-to-1 identical change pair.** The planner decomposed differently on the two models, so there is no single change you can pin "this took X tokens on 4.7, Y on 4.6." The comparison is clean *at the spec level* (same input → same expected output), but no change-level "this exact change" comparison exists.

2. **One spec, 5 runs.** This is one task type (Next.js + shadcn/ui + tailwind + Playwright micro-site). On a different stack (e.g., Python backend, mobile, fintech) the ratios may be different. Don't extrapolate the numbers here.

3. **The `ITERATION_END` event's `reason` field was unfilled** on the older runs (all `?`). So there is no structured answer to "what caused the iteration" — only the story reconstructed from journal step transitions and retry_context messages.

4. **The 4.7 0245 run's "3 paused/pending" count is partially not model-caused.** A run can also enter paused state from a watchdog timeout or user halt. I did not filter these out — the full run state is shown.

5. **Code quality is not measured.** The outputs (Next.js apps) merged on both sides through the verify gates, meaning lint + build + test + design-fidelity all passed. Whether the 4.7 or 4.6 produces better-quality code is not what these numbers say — only **how many tokens and iterations** it took to push it through the same gates.

6. **The "too creative" interpretation** for `blog-list-with-filter` (breaking a sibling spec) is **concrete, journal-recorded evidence**. But it does not logically follow that every 4.7 change wanders the same way. **One sample, hard evidence; population-level claim, no.** The 12-vs-5 decomposition and the 2.17× output-token total, on the other hand, are the full-run-level sample — that's the stronger claim.

7. **Cost estimates are deliberately omitted.** The exact output-token / input-token / cache-read pricing formula is time-of-day and version-specific; I don't want to misinform the reader with wrong dollar figures. The token ratio alone is enough.

8. **v0.app design drift is unquantified.** The `design-fidelity` gate's output in these runs was a placeholder (a 32-character stub on all 5 runs). The "4.7 is more prone to off-export component variants" observation is valid, but **only at a qualitative level** — concrete warning counts or critical counts cannot be read out of these state files. In future runs, substantive design-fidelity output would give this claim a measurable fingerprint.

---

## Source pointers

Every number is reproducible. Data files locally:

```
~/.local/share/set-core/e2e-runs/
  micro-web-run-20260501-1805/orchestration-state.json    # 4.7 ref
  micro-web-run-20260501-1805/orchestration-events.jsonl
  micro-web-run-20260501-1805/journals/blog-list-with-filter.jsonl   # the 292k anecdote
  micro-web-run-20260502-1104/orchestration-state.json    # 4.6 ref
  micro-web-run-20260502-1104/orchestration-events.jsonl
  micro-web-run-20260502-1104/journals/blog-pages.jsonl
```

Spec identity check:

```bash
sha256sum ~/.local/share/set-core/e2e-runs/micro-web-run-202605*/docs/spec.md
# all: ef1006c4b448...
```

Relevant commits on `set-core` `main`:

```
8cdcbd9f  feat(model-config): unified models block + opus-4-6 default
786fc27a  fix(model-config): translate short model pins to full claude CLI ids
db82ebb0  fix(model-config): purge hardcoded model fallbacks; opus alias → 4-6
fd9583be  fix(model-config): legacy directive defaults shadowed unified models block
```

---

## Thesis (what the data supports)

> Claude 4.7 is optimized for the consumer context: it infers a lot from a small input, "fills in" missing details, decomposes finely. These are virtues in single-shot use cases.
>
> In multi-agent orchestration, the same traits become liabilities. On the same spec, the planner LLM cuts the work into 12 chunks instead of 5. A feature agent breaks the spec test of another already-merged change because it "decided" the build pipeline needed touching too. Output token spend ends up at 2.17× for the same output.
>
> The 4.6 is not a more advanced model. **It is more conservative. More predictable. Less prone to "guessing what you meant."** In production orchestration that is the desired behavior — and the data shows it.
>
> The new shape of the `set-core` codebase (13 roles + 5-tier resolver + 40+ hardcoded-fallback purge) is the proof that this is not a default-flip problem. Every role gets an **explicit** model. The consumer stack and the production-orchestration stack **share the same API, but they are no longer solving the same problem.**
