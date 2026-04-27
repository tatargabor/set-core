## Context

Today the dispatcher injects review-learnings via a single text classifier (`classify_diff_content(scope)`) that was designed to scan diffs (`+++/---` markers, `prisma.`/`app.get(` patterns). At dispatch time there is no diff yet — only a scope description string — so the classifier always returns `set()`. The downstream `_build_review_learnings` callers treat empty as "include all", which means every change gets every learning ever recorded for any project.

Compounding this, `WebProjectType.rule_keyword_mapping` injects rule files (auth-middleware.md, security-patterns.md) on substring keyword match. `"token"` appears in "design tokens" (every shadcn scope) and `"route"` appears in "page routes" (every page-adding scope) — so every web change activates the auth and api categories.

Witness data: `micro-web-run-20260426-1302` produced 28 KB input.md per change, 45–65 % of which is auth/IDOR/Prisma/NextAuth content despite the project explicitly declaring "no auth, no API, no database, no Prisma." The current `blog-list-and-data` regression (3-column grid instead of v0's vertical list, missing Avatar in HoverCardTrigger, single CommandGroup instead of two) is partially attributable to the prompt dilution from this irrelevant context.

The set-core architecture (per `modular-architecture.md`) layers responsibility:

- **Layer 1** (`lib/set_orch/`): abstract orchestration, no project-specific patterns
- **Layer 2** (`modules/web/`): concrete web/Next.js patterns
- **Layer 3** (external plugins): private/community project types

Any redesign must respect this separation — concrete patterns (`next-auth`, `prisma`, `app/api`) cannot leak into Layer 1.

## Goals / Non-Goals

**Goals:**

1. Replace the buggy single-pass classification with a **per-change** multi-layer resolver that uses the change's own signals (change_type, REQ-IDs, manifest paths, scope intent, depends_on).
2. Add a **Sonnet 4.6 LLM classifier** as an additive last layer, with persistent cache + audit log + graceful fallback when the API call fails.
3. Build a **project-insights aggregator** so each merged change feeds back into the next dispatch's deterministic bias and into the LLM prompt context.
4. Keep all web-specific patterns in `modules/web/` — `lib/set_orch/` only owns orchestration, hooks, persistence, and LLM call infrastructure.
5. Backwards-compatible: plugins inheriting `CoreProfile` get safe no-op defaults; the dispatcher gracefully degrades when the LLM is unavailable.

**Non-Goals:**

- Pixel-level visual regression detection (handled by separate opt-in `pixel_diff` config).
- LLM-driven taxonomy expansion (Layer C of the original investigation): we record unknown categories the LLM proposes but do not auto-add them to the canonical taxonomy. That stays manual via `set-harvest`.
- Confidence-based escalation between Haiku and Sonnet (cascading models): out of scope for this change. Sonnet is the only LLM tier here. The deterministic layer is fast and free; Sonnet handles the long tail.
- Cross-project category propagation (sharing insights across projects): Layer C territory, not in this change.
- Replacing the diff-time `classify_diff_content` (it stays for verifier use on actual diffs).

## Decisions

### D1. Per-change signals dominate; project state is a fallback only

**Decision**: Five primary detection layers operate on **the change itself** (change_type, requirements, manifest paths, scope text, depends_on transitive). `detect_project_categories` (project state) is consulted only when the per-change signals yield ≤ 2 categories.

**Why**: Every change is a slice of a larger project. A "blog list page" change in a project that also has auth + payment + DB shouldn't receive IDOR/Prisma/payment learnings — those are sibling concerns. Per-change signals tightly bound the scope. Project state is informative only when the change is so thin it carries no domain signal of its own.

**Alternative considered**: Always union with project state. Rejected because it reproduces today's bloat in any large multi-domain project.

### D2. Six-layer detector union

**Decision**: The resolver computes a union over six deterministic layers:

1. `categories_from_change_type(change_type)` — phase defaults (foundational/feature/schema/...)
2. `categories_from_requirements(req_ids)` — REQ-prefix mapping (REQ-AUTH-* → auth)
3. `categories_from_paths(manifest_paths)` — file-path classification (`app/api/` → api)
4. `detect_scope_categories(scope)` — word-boundary intent regex
5. `categories_from_deps(depends_on)` — transitive closure of dependency categories from `project-insights.json`
6. `detect_project_categories(project_path)` — fallback only when (1)–(5) yield ≤ 2 entries

**Why**: Different changes leak signal through different channels. A foundational scaffolding change has weak scope text but strong change_type; a feature change has weak change_type but strong requirements. Union maximizes recall without overweighting any single signal.

**Alternative considered**: Weighted score with threshold instead of union. Rejected because category presence is binary (you either need auth learnings or you don't) and threshold tuning is fragile.

### D3. Sonnet 4.6 as additive LLM layer (not replacement)

**Decision**: After the deterministic layers run, a Sonnet 4.6 call is made with the scope, change_type, requirements, paths, deps, and project-insights summary. Its output is **unioned** with the deterministic result — Sonnet can only add categories, never remove.

**Why**:

- Sonnet's strength is implicit-dependency reasoning ("checkout flow" → auth + payment + db). Regex and prefix maps cannot capture that.
- Additive design means a hallucinated or wrong Sonnet response cannot suppress legitimate categories the deterministic layer already found. Worst case: Sonnet over-includes (mitigated by "be CONSERVATIVE" in the prompt and the union with already-conservative deterministic).
- Cost is bounded: ~$0.005/call, ~50 % cache-hit on retries, ~$0.03–0.06/run total.

**Alternative considered**:

- **Replace deterministic with LLM-only**: rejected. Adds API failure as a single point of failure. Removes the audit trail of "why was this category chosen" (deterministic reasons are inspectable, LLM reasoning is opaque).
- **Haiku 4.5 instead of Sonnet**: rejected. The user asked for Sonnet because the marginal accuracy on implicit-dependency cases (~1–2 pp) matters more than the 2.5× cost difference, which is still negligible in absolute terms.
- **Cascade Haiku → Sonnet on low confidence**: rejected for this iteration as premature optimization. Can be added later if cost grows.

### D4. Project-scoped feedback loop via insights aggregator

**Decision**: After each change merges, an aggregator walks `category-classifications.jsonl` and updates `project-insights.json` with:

- `by_change_type[change_type]` → common/rare categories observed in this project
- `scope_keyword_categories` → frequently-appearing scope words mapped to categories
- `deterministic_vs_llm.agreement_rate` → telemetry
- `uncovered_categories` → categories the LLM proposed that aren't in the taxonomy (for harvest)

The next dispatch's deterministic resolver consults `project-insights.json` to bias change-type defaults; the Sonnet prompt receives a one-paragraph summary as context.

**Why**: A project's character emerges from its first few changes. Once we've seen 3 `feature` changes in micro-web that always classify as `frontend` only, the next `feature` dispatch should default to `{frontend}` even before running detectors — and Sonnet should know "this project rarely involves auth/db/api" so it doesn't speculate.

**Alternative considered**: Cross-project shared insights file. Rejected because projects have wildly different shapes; pooling would either dilute (inject everything) or overfit to whatever project is loudest.

### D5. Strict Layer 1 / Layer 2 separation

**Decision**: All seven hook methods live on `ProjectType` (Layer 1) with no-op defaults. All concrete patterns (file paths, npm package names, scope keywords, REQ-prefixes, phase mappings, taxonomy contents, project summary) live in `WebProjectType` (Layer 2) overrides.

**Why**: Required by `modular-architecture.md`. A future Python or Go plugin must be able to deliver category resolution without forking core. The same dispatcher orchestration code calls profile hooks polymorphically.

**Alternative considered**: Put a "generic web defaults" set in Layer 1's `CoreProfile`. Rejected because `CoreProfile` is meant to provide universal rules only (3 verification rules, 4 directives that apply to every project regardless of stack). Web-specific extensions belong in the web plugin.

### D6. Cache by `sha256(scope || sorted(req_ids) || sorted(deps))`

**Decision**: The Sonnet call is cached on a hash of the inputs that determine the response. Retries, replans, and re-dispatches with the same input → cache hit, no API call.

**Why**: Replans regenerate input.md but the scope text usually stays identical. Without caching, every retry would burn another $0.005. With caching, the average per-run cost stays bounded even when the same change cycles through the verify pipeline 3–5 times.

**Cache invalidation**: never. The hash captures the full input; if scope changes, the hash changes and we get a fresh classification. Stale cache entries can accumulate but are negligible (~200 bytes each, JSONL append-only).

### D7. JSONL append-only audit trail at `.set/state/category-classifications.jsonl`

**Decision**: Every Sonnet call result (and the deterministic layers' outputs) gets appended to JSONL with timestamp, scope hash, deterministic categories, LLM categories, final union, agreement diff, model, duration, cost.

**Why**:

- Telemetry: how often does the LLM disagree with deterministic? If it's rarely, we can drop the LLM call.
- Debug: when a change gets a surprising category, the operator can grep the JSONL.
- Aggregator input: `insights.py` reads JSONL to compute project-insights.

**Why JSONL**: append-only, atomic per-line, tooling-friendly (grep/jq), no read/modify/write race with concurrent dispatchers.

### D8. Polysemous keywords removed from `rule_keyword_mapping`

**Decision**: Drop `token`, `middleware` from `auth.keywords`; drop `route` from `api.keywords`.

**Why**: These match design tokens, Next.js middleware (routing, not auth), and page routes — every web scope. Keeping them defeats any progress on category accuracy. The remaining keywords (`auth`, `login`, `session`, `cookie`, `password`; `api`, `endpoint`, `handler`, `REST`, `mutation`) are unambiguously domain-specific.

## Risks / Trade-offs

[Risk] **Sonnet hallucinates a category that doesn't exist** → Mitigation: the resolver filters Sonnet output against the profile's `category_taxonomy()`; unknown categories are logged to `uncovered_categories` for harvest review but are NOT injected into learnings (no broken learning lookup).

[Risk] **Sonnet over-includes despite "be CONSERVATIVE" prompt** → Mitigation: this regresses to today's behavior (over-injection). Acceptable fallback. Telemetry will show if it happens often enough to need prompt tuning.

[Risk] **API outage or rate-limit blocks dispatch** → Mitigation: 8-second timeout, single-shot retry, then graceful degradation to deterministic-only. Dispatch never blocks waiting for the LLM. Audit log records the fallback for telemetry.

[Risk] **Cache files grow unbounded over months of use** → Mitigation: JSONL is small (~200 bytes/entry × ~30 changes/run × ~10 runs/week = ~60 KB/week). At 1 MB after a year of heavy use, we add a lazy LRU truncation in `insights.py` (keep last 1000 entries). Not implemented in this change; deferred until a real project hits the limit.

[Risk] **Project-insights bias becomes self-reinforcing — once a project is mistakenly classified as "no auth", future auth-adding changes inherit weak detection** → Mitigation: the per-change signals dominate over project state in the resolver layering. A scope mentioning `oauth` triggers `detect_scope_categories` regardless of insights. Insights bias only informs the *defaults*, never overrides per-change signals.

[Risk] **Backwards-compatibility break for existing plugins that subclass `ProjectType` directly** → Mitigation: ABC defaults are no-ops, so unimplemented plugins lose category-aware injection but don't crash. Documented in proposal as **BREAKING** for direct subclassers; existing in-tree code uses `CoreProfile` which gets the defaults automatically.

[Risk] **Sonnet timeout adds 8 s to dispatch on API outage** → Mitigation: 8 s × ~30 changes/run = 4 min worst-case overhead per run, only when the API is fully down. Compared to 5400 s default change timeout, this is < 5 % overhead. Acceptable.

[Risk] **Cost runaway on a misconfigured project that re-dispatches the same change in a tight loop** → Mitigation: cache by scope hash means even a 1000-iteration loop spends $0.005 once. The poisoned-stall guard already exists at the engine layer to halt such loops; this change doesn't worsen that surface.

## Migration Plan

This is an additive change — no data migration required.

1. **Deploy phase 1**: Land Layer 1 ABC hooks with no-op defaults + `category_resolver.py` orchestration + dispatcher integration. At this point, `WebProjectType` is unchanged and returns no-ops, so the resolver always falls through to "include all" — same as today. No behavior change yet.

2. **Deploy phase 2**: Land `WebProjectType` overrides for the seven hooks. Categories now resolve per-change. Expect a sharp drop in input.md size for projects without auth/api/db.

3. **Deploy phase 3**: Land `insights.py` aggregator + dispatch-time consumption. Insights start populating from the next change merge onward. First few changes operate without insights bias (cold start).

4. **Rollback strategy**: Each phase is a separate commit. To revert to today's behavior, revert the dispatcher integration commit; the resolver and overrides become dead code but cause no harm.

## Open Questions

1. **Should `categories_from_deps` traverse depends_on transitively, or just one hop?** Decision: one hop for now (parent category set inherited). Transitive closure can be added if we observe insufficient propagation.

2. **Where does the LLM model selection live — in `lib/set_orch/category_resolver.py` as a constant, or as a profile property?** Decision: profile property (`profile.llm_classifier_model`). Default `"claude-sonnet-4-6"`. Profiles can downgrade to Haiku if cost is critical.

3. **Should we provide a `gate_overrides.category_resolver` config so operators can pin categories per-change?** Out of scope for this change; YAGNI until we hit a real escape-hatch case.
