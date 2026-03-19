## Context

The orchestration pipeline currently handles specs as single files. `find_input()` resolves to one `.md` file, `summarize_spec()` compresses it if >8K tokens, and the planner prompt receives a single `$input_content` variable. This worked for specs under ~500 lines but breaks down with multi-file product specs (30+ files, 3000+ lines) where cross-references between files carry critical implementation detail (SKU formats, variant systems, coupon rules, shipping zones).

Real-world evidence: the CraftBrew E2E scaffold has 34 files, 3511 lines, 25+ cross-file references, and a 14-change dependency graph. The current pipeline cannot process this without losing detail that determines correct change boundaries.

The pipeline is bash-based (planner.sh, dispatcher.sh, utils.sh) with Claude API calls for planning and optional agent-based decomposition via the decompose skill.

## Goals / Non-Goals

**Goals:**
- Multi-file spec input: `set-orchestrate plan --spec docs/` accepts a directory
- Structured digest output: requirements with IDs, domain summaries, cross-reference map
- Coverage tracking: every requirement mapped to a change, gaps detectable
- Spec context in worktrees: agents read original spec files during implementation
- Backward compatible: single-file specs work exactly as before

**Non-Goals:**
- Phased tasks.md with mid-apply checkpoints (separate future change)
- Cross-change context sharing beyond spec files (agents already get main branch code via depends_on)
- Requirement ID enforcement in user-written specs (digest generates IDs, user doesn't need to add them)
- Real-time digest updates during orchestration run (digest is created once before planning)

## Decisions

### D1: Digest as a separate orchestration phase

The digest runs as a distinct phase between "user writes spec" and "planner generates plan":

```
raw spec (user) → digest → plan → dispatch → execute
```

**Why not inline in planner?** The planner prompt is already large (~800 lines in planner.sh). Adding multi-file reading, subagent coordination, and requirement extraction would make it unmanageable. A separate phase also lets the user inspect and edit the digest before planning.

**Trigger:** Both explicit (`set-orchestrate digest --spec docs/`) and automatic (planner detects directory input without existing digest → runs digest first). The auto-trigger checks `wt/orchestration/digest/index.json` — if it exists and its `source_hash` matches current spec, skip re-digest.

**Single-file input:** If `--spec` resolves to a single file, `cmd_digest` treats it as a single-domain spec (one file = one domain) and proceeds normally. This lets users pre-generate a digest for any spec size.

### D2: Digest output structure (MD + JSON)

```
wt/orchestration/digest/
├── index.json              # file manifest, spec_base_dir, source hash, timestamps
├── conventions.json        # project-wide rules extracted from spec (i18n, SEO, design system, naming)
├── data-definitions.md     # catalog/seed data summary (entities, not behaviors)
├── requirements.json       # behavioral requirements with generated IDs
├── dependencies.json       # requirement→requirement relations
├── coverage.json           # requirement→change mapping (empty until plan)
├── ambiguities.json        # detected spec ambiguities, missing references, contradictions
└── domains/
    ├── <domain-1>.md       # human-readable domain summary
    ├── <domain-2>.md       # ...
    └── ...
```

**Why JSON for structured data?** The pipeline already depends on `jq` throughout. All structured digest files (index, requirements, dependencies, coverage, conventions) use JSON format, keeping `jq` as the only parser dependency. No `yq` required.

**Why MD for domain summaries and data definitions?** These are read by the planner (Claude) and by humans reviewing the digest. Markdown is natural for both.

**Domain grouping:** The digest agent groups spec files into domains heuristically (by directory structure if present, by topic if flat). Typically 3-6 domains — small enough that the planner sees all summaries at once.

**`conventions.json`:** Project-wide rules that apply to ALL changes (not just one). Examples: i18n routing patterns, SEO requirements, design system tokens, naming conventions, auth patterns, currency/locale settings. These are injected into every worktree's context, not per-change.

**`data-definitions.md`:** Summarizes catalog/inventory/seed data (product lists, user roles, categories) as reference material. Not behavioral requirements — agents use this to understand the data model without generating REQ-* IDs for each data entry.

### D3: Requirement ID generation

The digest agent reads spec files and identifies discrete requirements. Each gets an ID:

```json
// requirements.json
{
  "requirements": [
    {
      "id": "REQ-CART-001",
      "title": "Anonymous cart session",
      "source": "features/cart-checkout.md",
      "source_section": "Anonymous cart",
      "domain": "commerce",
      "brief": "Session-based cart using httpOnly cookie (UUID), persists without login"
    },
    {
      "id": "REQ-CART-002",
      "title": "Coupon validation",
      "source": "features/promotions.md",
      "source_section": "Coupon codes",
      "domain": "commerce",
      "brief": "3 coupon types with different rules (first-order, category-filter, expiry)"
    }
  ]
}
```

**ID format:** `REQ-{DOMAIN_SHORT}-{NNN}` — generated by the digest agent, not the user. The user writes natural language specs; the system adds traceability.

**Granularity:** One requirement = one independently testable behavior. "Cart supports coupons" is too broad; "ELSO10 coupon gives 10% on first order only" is right. The digest agent uses this heuristic: if it needs its own test case, it's a requirement.

### D4: Planner reads digest instead of raw spec

When digest exists, `find_input()` in `lib/orchestration/utils.sh` returns `INPUT_MODE="digest"` and `INPUT_PATH` points to the digest directory. The new branch in `find_input()`:

```bash
# utils.sh find_input() — new directory branch
if [[ -d "$SPEC_OVERRIDE" ]]; then
    INPUT_MODE="digest"
    INPUT_PATH="$(cd "$SPEC_OVERRIDE" && pwd)"
    return 0
fi
```

The planner prompt template in `lib/orchestration/planner.sh` `cmd_plan()` gets a new section:

```
## Project Conventions (apply to ALL changes)
<conventions.json content>

## Data Model Reference
<data-definitions.md content>

## Spec Digest
### Structure
<index.json content — including execution_hints if present>

### Domain Summaries
<domains/*.md concatenated>

### Requirements (N total)
<requirements.json content>

### Cross-references
<dependencies.json content>
```

This replaces the current `$input_content` (raw/summarized spec). Conventions and data definitions appear first so the planner sees project-wide rules before feature-specific requirements. Execution hints (if present) provide optional guidance about implementation order from the spec author. The planner also gets a new output field per change:

```json
{
  "name": "cart-feature",
  "spec_files": ["features/cart-checkout.md", "features/promotions.md"],
  "requirements": ["REQ-CART-001", "REQ-CART-002", "REQ-PROMO-001"],
  "also_affects_reqs": ["REQ-I18N-003"]
}
```

The `also_affects_reqs` field lists cross-cutting requirements that this change must incorporate but does not own. The owning change implements the foundation; `also_affects` changes integrate with it.

**Coverage validation:** After plan generation, a bash function iterates requirements.json and checks every ID appears in at least one change's `requirements[]`. Cross-cutting requirements in `also_affects_reqs` are validated to have a primary owner. If uncovered requirements exist → warning (not hard fail, as some may be deferred to future phases).

### D5: Spec context dispatch to worktrees

When `dispatch_change()` in `lib/orchestration/dispatcher.sh` runs, it reads `spec_files[]` from the state for that change and copies the raw spec files. The spec base directory is resolved from `index.json`:

```bash
# dispatcher.sh — dispatch_change() addition
local digest_dir="wt/orchestration/digest"
local spec_base_dir
spec_base_dir=$(jq -r '.spec_base_dir' "$digest_dir/index.json")

local spec_files
spec_files=$(jq -r --arg n "$change_name" \
    '.changes[] | select(.name == $n) | .spec_files[]' "$STATE_FILENAME")

if [[ -n "$spec_files" ]]; then
    mkdir -p "$wt_path/.claude/spec-context"
    while IFS= read -r sf; do
        local target_dir="$wt_path/.claude/spec-context/$(dirname "$sf")"
        mkdir -p "$target_dir"
        cp "$spec_base_dir/$sf" "$target_dir/"
    done <<< "$spec_files"
fi
```

The `spec_base_dir` is stored in `index.json` at digest time (absolute path to the spec directory root). This ensures correct resolution even when dispatch happens from a different working directory.

The pre-created proposal.md gets additional sections:

```markdown
## Source Specifications
Read these for detailed requirements:
- `.claude/spec-context/cart-checkout.md` — checkout flow details
- `.claude/spec-context/promotions.md` — coupon validation rules

## Requirements
This change covers:
- REQ-CART-001: Anonymous cart session — Session-based cart using httpOnly cookie
- REQ-CART-002: Coupon validation — 3 coupon types with different rules
```

Additionally, the dispatcher copies `conventions.json` and `data-definitions.md` from the digest to **every** worktree (not just changes that list them in `spec_files[]`):

```bash
# dispatcher.sh — conventions dispatch (always, if digest exists)
if [[ -f "$digest_dir/conventions.json" ]]; then
    cp "$digest_dir/conventions.json" "$wt_path/.claude/spec-context/"
fi
if [[ -f "$digest_dir/data-definitions.md" ]]; then
    cp "$digest_dir/data-definitions.md" "$wt_path/.claude/spec-context/"
fi
```

This is lightweight (file copy, no API calls) and gives the agent direct access to the exact spec sections it needs, plus project-wide conventions that apply to all changes.

### D6: Digest uses Claude API, not subagents (for now)

**Alternative considered:** Parallel subagents per domain (one Explore agent per directory).

**Decision:** Single Claude API call with structured prompt. A 3500-line spec with ~8 words/line = ~28K words ≈ ~36K tokens (using the pipeline's `estimate_tokens()` formula: words × 1.3). This is well within Claude's context window. Subagent coordination adds complexity for marginal benefit at this scale.

**Future:** If specs exceed ~8000 lines (~75K tokens), add a `digest_method: agent` directive (parallel to `plan_method: agent`) that uses subagents. But don't build this now — YAGNI.

### D7: coverage.json lifecycle

```
digest phase:   requirements.json created, coverage.json = empty {}
plan phase:     populate_coverage() fills coverage.json (requirement → change mapping, status: planned)
dispatch phase: update_coverage_status() → dispatched (in dispatcher.sh)
running phase:  update_coverage_status() → running (in monitor.sh)
merge phase:    update_coverage_status() → merged (in merge handler)
completion:     set-orchestrate coverage shows full report
```

```json
// coverage.json
{
  "coverage": {
    "REQ-CART-001": { "change": "cart-feature", "status": "planned" },
    "REQ-CART-002": { "change": "cart-feature", "status": "merged" },
    "REQ-SUB-001": { "change": "subscription", "status": "running" },
    "REQ-I18N-001": { "change": "project-infra", "status": "planned", "also_affects": ["user-auth", "email"] }
  },
  "uncovered": []
}
```

Status values: `planned` → `dispatched` → `running` → `merged`. Each transition requires an explicit `update_coverage_status()` call at these hook sites:

| Transition | Function | File |
|------------|----------|------|
| → `planned` | `populate_coverage()` | `lib/orchestration/digest.sh` (after plan generation) |
| → `dispatched` | `update_coverage_status()` | `lib/orchestration/dispatcher.sh` (in `dispatch_change()`) |
| → `running` | `update_coverage_status()` | `lib/orchestration/monitor.sh` (when loop starts producing commits) |
| → `merged` | `update_coverage_status()` | `lib/orchestration/merger.sh` or merge handler (after successful merge) |

### D8: Re-digest ID stability

When re-running digest on modified specs, the system must preserve existing requirement IDs to keep coverage.json references valid.

**Algorithm:**
1. Load existing `requirements.json` if present
2. For each requirement in new digest output, match against existing by `source` + `source_section`
3. If matched → reuse existing ID
4. If new (no match) → assign next available ID in that domain
5. If removed (existing ID not in new output) → keep in requirements.json with `"status": "removed"`
6. Write updated requirements.json with stable IDs

**Limitation:** If a user renames a spec section heading, the match fails and a new ID is generated. The old ID becomes `status: removed` and coverage.json retains an orphan reference. This is acceptable — the `set-orchestrate coverage` report shows orphaned requirements so the user can manually reconcile.

### D9: Spec file classification

The digest agent classifies each spec file into one of four categories before extracting requirements. This prevents conflating project conventions with feature behaviors, or treating seed data as testable requirements.

**Classification scheme:**

| Category | Description | Digest output | Example |
|----------|-------------|---------------|---------|
| `convention` | Project-wide rules that apply to every change | `conventions.json` | i18n routing, SEO patterns, design system tokens, naming |
| `feature` | Behavioral requirements for specific functionality | `requirements.json` + `domains/*.md` | cart operations, subscription management, admin CRUD |
| `data` | Entity/inventory definitions, seed data, catalogs | `data-definitions.md` | product catalogs, user roles, categories |
| `execution` | Implementation plan, change scoping, dependency graphs | Stored in `index.json` as `execution_hints` | change specs (C01-C14), verification checklists |

**Classification heuristic (in digest prompt):**
- Files defining rules/patterns that span multiple features → `convention`
- Files describing what a specific feature does (behaviors, user stories, flows) → `feature`
- Files listing entities, items, or seed data with attributes → `data`
- Files describing implementation order, change scope, or acceptance checklists → `execution`

**Why this matters:** Without classification, a 30-file spec produces ~280 REQ-* IDs, many of which are data entries (individual products) or restatements of conventions. With classification, `requirements.json` contains only behavioral requirements (~120-150 IDs), conventions are injected globally, and data definitions serve as reference. This makes the planner's coverage mapping significantly more accurate.

**Convention dispatch:** Unlike feature spec files which go to specific worktrees via `spec_files[]`, conventions are copied to **every** worktree as `.claude/spec-context/conventions.json`. The dispatcher reads this from digest output and copies it alongside change-specific spec files.

**Execution hints:** Files classified as `execution` are stored in `index.json`'s `execution_hints` field. The planner can use these as soft guidance (suggested change boundaries, dependency ordering) without treating them as hard requirements. This is valuable when the spec author has pre-planned the implementation order.

### D10: Cross-cutting requirement ownership

Some requirements (i18n integration, responsive layout, auth checks) inherently span multiple changes. The coverage model supports this via `also_affects`:

```json
{
  "coverage": {
    "REQ-I18N-001": {
      "change": "project-infra",
      "status": "planned",
      "also_affects": ["user-auth", "email-notifications"]
    }
  }
}
```

**Primary ownership:** One change "owns" the requirement (creates the foundation). **`also_affects`:** Other changes that must incorporate this requirement's constraints. The planner assigns both.

**Why not split into sub-IDs?** Cross-cutting requirements are naturally indivisible ("all routes must support HU/EN"). Splitting into `REQ-I18N-001a`, `REQ-I18N-001b` etc. would create artificial fragmentation. Instead, the primary change implements the foundation and `also_affects` changes must be aware of it.

**Convention vs. cross-cutting requirement:** If a rule applies identically to all changes without change-specific adaptation, it's a `convention` (goes in `conventions.json`). If it requires per-change implementation work (e.g., "add i18n routes for this feature's pages"), it's a cross-cutting requirement with `also_affects`.

### D11: Verification checklist de-duplication

Master spec files often contain verification checklists (acceptance criteria) that overlap with detailed requirements in feature files. The digest must not produce duplicate REQ-* IDs.

**Algorithm:**
1. Process feature files first → generate REQ-* IDs from detailed behavioral descriptions
2. Process master file's verification checklist second → match each checklist item against existing REQ-* IDs by semantic similarity
3. If a checklist item matches an existing REQ-* → skip (don't create duplicate)
4. If a checklist item describes a behavior not found in any feature file → create a new REQ-* (this catches requirements only mentioned in the checklist)

**Example:** v1-craftbrew.md says "Coffee catalog page shows 8 products in responsive grid". product-catalog.md has the same requirement in detail. The digest creates ONE REQ-CATALOG-001, not two.

**Why this matters:** Without de-duplication, a 17-file spec with a 46-item verification checklist produces ~300 raw items → ~240 unique after de-dup. With de-dup in the prompt, the digest directly produces ~230-240 clean IDs.

### D12: Ambiguity detection and reporting

The digest agent SHALL identify underspecified, contradictory, or ambiguous requirements and report them in a separate `ambiguities.json` file.

```json
// ambiguities.json
{
  "ambiguities": [
    {
      "id": "AMB-001",
      "type": "underspecified",
      "source": "catalog/coffees.md",
      "section": "Variant System",
      "description": "Drip bag pricing formula unclear: 'base+500 / base x2+500' — does 'base' mean 250g price?",
      "affects_requirements": ["REQ-CATALOG-003"]
    },
    {
      "id": "AMB-002",
      "type": "missing_reference",
      "source": "features/subscription.md",
      "section": "Payment Failure",
      "description": "References 'payment failure email' but no template defined in email-notifications.md",
      "affects_requirements": ["REQ-SUB-015"]
    }
  ]
}
```

**Ambiguity types:**
- `underspecified` — behavior described but details missing (e.g., merge strategy for cart items)
- `contradictory` — two files describe the same thing differently
- `missing_reference` — one file references a behavior/template/entity that doesn't exist in the referenced file
- `implicit_assumption` — behavior depends on an undeclared dependency

**Usage:** The planner includes `ambiguities.json` in its prompt, allowing it to make explicit decisions for ambiguous cases or flag them for human review. `set-orchestrate digest --dry-run` shows ambiguities to the user before committing.

### D13: Embedded behavioral rules in data files

Data files (catalogs, seed data) frequently embed behavioral rules alongside entity definitions. The digest must extract these as REQ-* IDs even though the file is primarily classified as `data`.

**Examples from real-world spec:**
- `coffees.md` (data) contains variant system rules (form × size matrix, price modifiers) → behavioral
- `merch.md` (data) contains gift card mechanics (code format, partial use, expiry) → behavioral
- `bundles.md` (data) contains stock calculation rule (min of components) → behavioral

**Prompt instruction:** "Data files may contain embedded behavioral rules (business logic, calculations, validation rules, state machines). Extract these as REQ-* IDs in requirements.json. The file-level classification remains `data` (it goes to data-definitions.md), but the embedded behavioral rules get separate REQ-* entries with `source` pointing to the data file."

This is critical because without it, the gift card mechanics in merch.md or the variant pricing in coffees.md would be lost — they'd be summarized as data but never tracked as implementable requirements.

## Risks / Trade-offs

**[Risk] Digest quality depends on Claude's requirement extraction accuracy**
→ Mitigation: The digest is human-reviewable (MD + YAML). User can edit requirements.json before planning. `set-orchestrate digest --dry-run` shows what would be generated without writing.

**[Risk] Stale digest after spec edits**
→ Mitigation: `index.json` stores `source_hash` (SHA256 of all spec files concatenated). Planner checks hash match — if stale, auto-re-digests or warns.

**[Risk] Requirement ID instability across re-digests**
→ Mitigation: Re-digest tries to match existing IDs by source file + section title. New requirements get new IDs, removed ones are marked `status: removed` in requirements.json (not deleted). Coverage.yaml references remain stable.

**[Risk] Large spec files exceed single API call context**
→ Mitigation: For now, specs up to ~5000 lines (~50K tokens) work in one call. If exceeded, fall back to summarize-per-file approach (each file summarized individually, then merged). The D6 subagent approach is the escape hatch if this isn't enough.

**[Risk] Spec section renames break ID matching on re-digest**
→ Mitigation: Re-digest match is by `source` + `source_section`. If a user renames a section, old ID becomes `status: removed` and a new ID is generated. `set-orchestrate coverage` reports orphaned coverage entries so the user can reconcile. No silent data loss — just a warning.

**[Trade-off] Extra step in pipeline**
→ The digest adds ~30-60 seconds to the orchestration start. Acceptable given it saves hours of agent misdirection from lost spec context.

**[Trade-off] Backward compatibility surface**
→ Single-file specs bypass digest entirely (existing `INPUT_MODE="spec"` path unchanged). No risk to current workflows.
