# Design: domain-parallel-decompose

## Context

The current planning pipeline (`run_planning_pipeline()` in `planner.py`) makes a single Claude call with all spec content, digest data, and context concatenated into one prompt. The digest system already structures data by domain (`domains/`, `requirements.json` with `domain` field), but the planner doesn't leverage this structure.

The pipeline outputs `orchestration-plan.json` consumed by engine/dispatcher/verifier. This output format stays unchanged.

## Goals / Non-Goals

**Goals:**
- Split decompose into 3 phases: brief → domain-decompose → merge
- Run Phase 2 in parallel (one opus call per domain)
- Better quality via smaller, focused context per domain
- Selective replan — re-run only what's needed

**Non-Goals:**
- Changing `orchestration-plan.json` format
- Inter-agent messaging during Phase 2
- Sub-domain splitting
- Changing the digest pipeline

## Decisions

### D1: Phase 1 — Planning Brief

**Input:** Domain summaries (from `domains/`), `dependencies.json`, `conventions.json`, test infra context, existing specs, active changes, memory context.

**Prompt structure:**
```
You are planning a software project decomposition.

Given these domain summaries and cross-domain dependencies,
produce a planning brief that will guide per-domain decomposition agents.

[domain summaries — compact, ~200 words each]
[dependencies.json]
[conventions.json]
[test infra]
[existing specs summary]
[active changes]

Output JSON:
{
  "domain_priorities": ["schema", "auth", ...],
  "resource_ownership": {
    "prisma/schema.prisma": {"owner": "schema", "note": "migrations only"},
    "src/middleware.ts": {"owner": "auth", "note": "auth middleware"},
    ...
  },
  "cross_cutting_changes": [
    {"name": "i18n-setup", "scope": "...", "affects_domains": ["catalog", "cart"]}
  ],
  "phasing_strategy": "Infrastructure and schema first, then auth, then features in parallel",
  "domain_constraints": {
    "catalog": "Do NOT plan schema migrations — schema domain handles those",
    "cart": "Depends on auth middleware from auth domain"
  }
}
```

**Why JSON:** Downstream agents parse it deterministically. Free text would require re-interpretation.

**Token budget:** ~10K input (domain summaries are compact), ~2K output. Fast call.

### D2: Phase 2 — Domain Decompose

**Per-domain input:**
- Domain requirements (from `requirements.json`, filtered by `domain` field)
- Domain summary (from `domains/<domain>.json`)
- Planning brief (from Phase 1)
- Conventions (from `conventions.json`)
- Test infra context
- Planning rules (same `_PLANNING_RULES_CORE` as current)

**Per-domain output:** Same change format as current plan, but only for this domain:
```json
{
  "changes": [
    {
      "name": "product-listing-pages",
      "scope": "...",
      "complexity": "M",
      "change_type": "feature",
      "requirements": ["REQ-CAT-001", "REQ-CAT-002"],
      "model": "opus",
      "has_manual_tasks": false,
      "gate_hints": {},
      "external_dependencies": [
        {"resource": "prisma/schema.prisma", "owner_domain": "schema", "need": "ProductCategory enum"}
      ]
    }
  ]
}
```

**`external_dependencies`:** New field — when a domain agent needs a resource it doesn't own (per the brief), it declares the dependency here. Phase 3 resolves these into `depends_on` edges.

**Parallel execution:** Use `concurrent.futures.ThreadPoolExecutor` with `max_workers=min(len(domains), 6)`. Each thread calls `run_claude()` independently. Results collected via `as_completed()`.

**Token budget per domain:** ~8K input (domain reqs + brief + conventions + rules), ~3K output. Much smaller than the current 50K single call.

### D3: Phase 3 — Merge & Resolve

**Input:**
- All domain plans (concatenated)
- Planning brief (from Phase 1)
- `dependencies.json` (cross-domain requirement dependencies)
- Ambiguities resolution context

**Tasks for the merge agent:**
1. **Resolve `external_dependencies`** → create `depends_on` edges between changes
2. **Detect conflicts** — two changes touching same files → serialize with `depends_on` or merge
3. **Add cross-cutting changes** from the brief (i18n, config, etc.)
4. **Assign phases** — topological sort on the full dependency graph
5. **Validate coverage** — every req in `requirements.json` must appear in exactly one change's `requirements` list
6. **Fill metadata** — `plan_version`, `brief_hash`, `reasoning`, `phase_detected`

**Output:** Standard `orchestration-plan.json` — same schema as current.

**Token budget:** ~15K input (all domain plans are compact lists + brief), ~10K output (full plan). This is smaller than the current single-call because it only sees change summaries, not the full spec.

### D4: Threading model

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _phase2_parallel(domains, brief, conventions, rules, test_infra):
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(domains), 6)) as pool:
        futures = {
            pool.submit(_decompose_domain, domain, brief, conventions, rules, test_infra): domain
            for domain in domains
        }
        for future in as_completed(futures):
            domain = futures[future]
            results[domain] = future.result()  # raises if domain failed
    return results
```

If any domain fails, the entire Phase 2 fails and raises. No partial results — we need all domains for Phase 3.

### D5: Selective replan strategy

Store the Phase 1 brief and Phase 2 per-domain results in the planning state so replan can selectively re-run:

```
orchestration-plan.json          ← final merged plan (unchanged)
orchestration-plan-domains.json  ← NEW: per-domain Phase 2 results + brief
```

The `orchestration-plan-domains.json` file stores:
```json
{
  "brief": { ... },
  "domain_plans": {
    "catalog": { "changes": [...] },
    "cart": { "changes": [...] },
    ...
  }
}
```

Replan reads this, re-runs only the needed domains in Phase 2, then re-runs Phase 3 with the updated domain plans.

### D6: Backward compatibility

- `run_planning_pipeline()` interface stays the same — callers see no change
- Output `orchestration-plan.json` schema stays the same
- `populate_coverage()` works unchanged — it reads the final plan
- `validate_plan()` works unchanged — it validates the final plan
- Brief and spec input modes: for non-digest mode (no domains), create a single synthetic domain containing all requirements and run the same 3-phase flow

## Risks / Trade-offs

- **[Risk] More API calls = more cost** → Mitigation: each call is smaller, total tokens may be similar or lower. The quality improvement justifies the marginal cost increase.
- **[Risk] Phase 2 thread failure** → Mitigation: if any domain fails, entire Phase 2 fails cleanly. Retry logic at pipeline level.
- **[Risk] Phase 3 merge quality** → Mitigation: the merge input is compact (change lists, not full specs), which is easier for the model than the current monolithic input.
- **[Risk] `orchestration-plan-domains.json` bloat** → Mitigation: this file only contains change summaries, not spec content. Typically <50KB.

## Open Questions

_None._
