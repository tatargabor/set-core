# Design: Plugin Deploy Architecture

## Goals / Non-Goals

**Goals:**
- set-core has zero knowledge of specific project types (no hardcoded "web", "python", etc.)
- Plugins fully control which rules get deployed to consumer projects
- All defined plugin interface methods are wired into their corresponding engine components
- Any third-party plugin can extend the system without modifying set-core

**Non-Goals:**
- Creating new project type plugins (set-project-python, set-project-mobile)
- Changing the entry_points plugin discovery mechanism
- Redesigning the template deployment mechanism (deploy_templates stays)

## Decisions

### D1: Web Rules Move to Plugin Package

**Decision:** Migrate all 7 `set-core/.claude/rules/web/*.md` files to `set-project-web/set_project_web/templates/nextjs/framework-rules/web/`.

**Alternatives:**
- Keep rules in set-core, let profile specify which subdirs to deploy → set-core still owns project-type-specific content
- Deploy manifest JSON (plugin writes, bash reads) → unnecessary intermediate format

**Rationale:** The modular architecture principle says "never hardcode project-specific patterns in set-core core." Rule files are project-specific content. The plugin already has a template directory mechanism that handles file deployment. Moving rules there eliminates the cross-mechanism split entirely.

### D2: Python Handles All Plugin Rule Deployment

**Decision:** The existing `deploy_templates()` in `set-project-base/deploy.py` handles both template rules AND framework rules. deploy.sh only deploys top-level generic rules from set-core.

**Alternatives:**
- Manifest-based: plugin writes JSON, deploy.sh reads and copies → Rube Goldberg (bash↔JSON↔Python bridge)
- All-Python deploy: move ALL rule deployment to Python → too large a change, deploy.sh handles skills/agents/CLAUDE.md too

**Rationale:** The Python deploy mechanism already exists, is well-tested, and has manifest/module support. Extending it with one new `_PATH_MAPPINGS` entry is minimal effort. deploy.sh keeps its role for non-plugin content (generic rules, skills, agents).

### D3: Framework Rules Use `set-` Prefix

**Decision:** Files under `framework-rules/` in the plugin template get deployed with `set-` prefix (e.g., `auth-middleware.md` → `set-auth-middleware.md`). Template `rules/` files do not get the prefix.

**Alternatives:**
- No prefix distinction → user can't tell which rules came from the framework vs template
- All rules get prefix → breaks existing template rule references

**Rationale:** The prefix already exists in the current deploy.sh flow. Maintaining it preserves backward compatibility and lets users identify framework-provided rules.

### D4: `_PATH_MAPPINGS` Extension in deploy.py

**Decision:** Add `"framework-rules/"` mapping to `_PATH_MAPPINGS` in `set-project-base/deploy.py`:

```python
_PATH_MAPPINGS = {
    "rules/": ".claude/rules/",
    "framework-rules/": ".claude/rules/",
}
```

The `_target_path()` function applies the `set-` prefix for files coming from `framework-rules/`:

```python
def _target_path(template_rel: str, target_dir: Path) -> Path:
    # framework-rules/ → .claude/rules/ with set- prefix
    if template_rel.startswith("framework-rules/"):
        rel = template_rel[len("framework-rules/"):]
        parent = Path(rel).parent
        name = Path(rel).name
        dst_dir = target_dir / ".claude" / "rules" / parent
        return dst_dir / f"set-{name}"

    # ... existing mappings
```

**Rationale:** Keeps the prefix logic in one place. The deploy mechanism already handles path remapping; this is a natural extension.

### D5: deploy.sh Simplified to Top-Level Only

**Decision:** deploy.sh rule loop uses `find -maxdepth 1` to deploy only top-level `.md` files from `set-core/.claude/rules/`. No subdirectory traversal, no type checks.

```bash
while IFS= read -r -d '' src_file; do
    base_name=$(basename "$src_file")
    cp "$src_file" "$dst_rules/set-$base_name"
    rule_count=$((rule_count + 1))
done < <(find "$src_rules" -maxdepth 1 -name '*.md' -print0)
```

**Rationale:** After web rules move to the plugin, set-core has only generic rules at top level (cross-cutting-checklist.md, modular-architecture.md, etc.). The `gui/` skip and `web/` type-check are both eliminated. Simpler code, no project-type awareness.

### D6: NullProfile Returns Empty for All Methods

**Decision:** `NullProfile` in `profile_loader.py` returns `{}` for `rule_keyword_mapping()` and `[]` for all list-returning methods. No web-specific content.

**Rationale:** NullProfile is a safety net for when no plugin is loaded. Since `set-project init` always requires a project type, NullProfile should only fire during development or misconfiguration. Empty returns mean no false rule injections.

### D7: Engine Wiring Pattern (Phase 2-5)

**Decision:** All engine integrations follow the same pattern:

```python
# In the engine component (verifier, merger, engine, templates)
profile = load_profile()
result = profile.<method_name>()
if result:
    # use result
```

Each method:
1. Added to `NullProfile` returning empty ([] or {})
2. Already defined in `set-project-base/base.py` ABC
3. Already implemented in `set-project-web/project_type.py`
4. Wired into the corresponding engine component with a simple call

**Rationale:** This is the established pattern (see `planning_rules()`, `gate_overrides()`, `rule_keyword_mapping()`). No new abstractions needed.

### D8: Verification Rules Runtime Loading

**Decision:** Verifier calls `profile.get_verification_rules()` at evaluation time, not at startup. Rules are not cached — each verify gate call gets fresh rules from the profile.

The existing `evaluate_verification_rules()` in verifier.py (line 1235) already loads rules from `project-knowledge.yaml`. The plugin rules augment this: profile rules are merged with YAML-defined rules, with profile rules taking precedence on ID collision.

**Rationale:** Runtime loading avoids staleness. The verifier already has a rules evaluation pipeline; plugin rules feed into the same pipeline.

### D9: Merge Strategies Wiring

**Decision:** `merger.py` calls `profile.merge_strategies()` before executing `set-merge`. The returned strategies define file-pattern → merge-behavior mappings:

```python
strategies = profile.merge_strategies()
# Example return:
# [{"patterns": ["*.lock", "pnpm-lock.yaml"], "strategy": "theirs"},
#  {"patterns": ["prisma/schema.prisma"], "strategy": "ours"}]
```

The merger passes these to `set-merge` as flags or applies them pre-merge.

**Rationale:** Interface already exists and is implemented in WebProjectType. Only the merger-side call is missing.

### D10: Decompose Hints as Plain Text

**Decision:** `decompose_hints()` returns `list[str]` — each string is a self-contained natural language instruction appended to the planning prompt.

```python
def decompose_hints(self) -> list[str]:
    return [
        "For each product category in the database schema enum, ...",
        "Every new user-facing route must have a corresponding i18n key task.",
    ]
```

Planner appends these after `_get_planning_rules()` output.

**Rationale:** Self-describing hints keep plugin logic in the plugin. No registry of hint types in core. The plugin author writes exactly the prompt text they want the planner to see.

## Architecture

### Deploy Flow (After Migration)

```
set-project init <type>
    │
    ├── deploy.sh ──────────────────────────────┐
    │   ├── top-level rules: maxdepth 1         │  GENERIC ONLY
    │   │   cross-cutting-checklist.md → set-*  │  no subdir awareness
    │   │   modular-architecture.md → set-*     │
    │   ├── skills → .claude/skills/            │
    │   ├── agents → .claude/agents/            │
    │   └── CLAUDE.md                           │
    │                                           │
    ├── Python: deploy_templates() ─────────────┤
    │   ├── template rules/ → .claude/rules/    │  PLUGIN-CONTROLLED
    │   │   auth-conventions.md (no prefix)     │
    │   │   ui-conventions.md (no prefix)       │
    │   ├── framework-rules/ → .claude/rules/   │
    │   │   web/auth-middleware.md → set-*       │  set- prefix
    │   │   web/security-patterns.md → set-*    │
    │   └── project-knowledge.yaml              │
    │                                           │
    └── project-type.yaml ← saves type+modules │
```

### Engine Integration Points

```
                    NullProfile (safety net)
                    ┌──────────────────────────────────┐
                    │ rule_keyword_mapping() → {}       │
                    │ get_verification_rules() → []     │
                    │ get_orchestration_directives() → []│
                    │ merge_strategies() → []           │
                    │ decompose_hints() → []            │
                    └──────────────┬───────────────────┘
                                   │ (fallback)
                                   │
                    PluginProfile (e.g. WebProjectType)
                    ┌──────────────────────────────────┐
                    │ rule_keyword_mapping() → {web..}  │──► dispatcher.py
                    │ get_verification_rules() → [8..]  │──► verifier.py
                    │ get_orchestration_directives()→[7]│──► engine.py
                    │ merge_strategies() → [{lock..}]   │──► merger.py
                    │ decompose_hints() → ["For each.."]│──► templates.py
                    └──────────────────────────────────┘
```

## Cross-Repo Dependency Order

Changes must be applied in this order to avoid breakage:

```
1. set-project-base: _PATH_MAPPINGS + _target_path() prefix logic
   │
2. set-project-web: add framework-rules/web/ + update manifest.yaml
   │  (at this point, new mechanism works but old one still exists)
   │
3. set-core: delete .claude/rules/web/, simplify deploy.sh,
   │          clean NullProfile, wire engine methods
   │  (old mechanism removed, new mechanism is sole path)
```

Phase 2-5 (engine wiring) are independent of Phase 1 and of each other. They can be done in any order after NullProfile methods are added.
