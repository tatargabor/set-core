## Context

The current design pipeline assumes `v0-export/` lives inside the project root. The dispatcher's `_deploy_v0_export_to_worktree()` (dispatcher.py:472) creates a symlink `<wt>/v0-export → <project>/v0-export`. The profile's `detect_design_source()` also only searches the project directory.

For projects like consumer-app, the design lives in a separate repo (`~/projects/consumer-app-design`) with its own git history, shadcn/ui components, design tokens in `globals.css`, and design rules in `.set-designer/design-rules/`. The code project at `~/code/consumer-app` has no `v0-export/` directory — the design source is external.

The design pipeline in set-core is controlled by:
- `design_pipeline` directive in orchestration.yaml (auto/none) — config.py:144
- `profile.detect_design_source()` — returns source identifier or "none"
- `profile.has_design_pipeline()` — checks directive then delegates to detect
- `profile.get_design_dispatch_context()` — builds markdown for agent input.md
- `_deploy_v0_export_to_worktree()` — symlinks design tree into worktree

## Goals / Non-Goals

**Goals:**
- Support external design directories via `design_source_path` directive in orchestration.yaml
- Adapt v0-export symlink logic to mount external directories
- Extract design tokens from external repo's CSS into agent-consumable format
- Load `.set-designer/design-rules/*.md` from external repo as agent rules
- Work with existing `has_design_pipeline` / `detect_design_source` pattern

**Non-Goals:**
- Multi-repo git sync (the external design repo is read-only reference)
- Design token diffing or change detection between design versions
- Automatic design-to-component mapping (that's `design-component-binding`)
- Figma/Penpot MCP integration (separate feature)

## Decisions

### D1: New directive `design_source_path` in orchestration.yaml

```yaml
design_pipeline: auto
design_source_path: ~/projects/consumer-app-design
```

When `design_source_path` is set:
- `detect_design_source()` checks the external path first, returns `"v0-external"` if found
- `_deploy_v0_export_to_worktree()` symlinks external path instead of `<project>/v0-export`
- Falls back to in-project `v0-export/` if external path doesn't exist (log warning)

This is a config.py change: add `"design_source_path": None` to DIRECTIVE_DEFAULTS and a string validator to `_VALIDATORS`.

### D2: Design token extraction from globals.css

The external design repo's `app/globals.css` contains CSS custom properties (OKLCH color space) and `@theme` blocks. The bridge extracts these into a `design-system.md` that agents can consume:

```
## Design Tokens (auto-extracted from external design repo)

### Colors
- --background: oklch(0.985 0 0)
- --primary: oklch(0.205 0 0)
...

### Typography
- Font: Geist Sans, Geist Mono
- Base radius: 0.5rem
```

Extraction happens at dispatch time, not at startup — design tokens may change between dispatches. The result is injected into `get_design_dispatch_context()` output.

Implementation: regex parse `:root { ... }` and `.dark { ... }` blocks. No CSS parser dependency needed — the format is predictable (shadcn/ui convention).

### D3: Design rules injection

The external repo's `.set-designer/design-rules/*.md` files (8 files: color-tokens, component-library, tailwind-tokens, naming-conventions, form-patterns, layout-presets, accessibility, data-architecture) are injected into the worktree's `.claude/rules/` at dispatch time.

Method: symlink each rule file from external repo into worktree's `.claude/rules/design-<name>.md`. This is analogous to how `_build_rule_injection()` loads category-matched rules, but these are always injected for design-pipeline projects.

### D4: WebProjectType override, not core change

The external path resolution lives in `modules/web/set_project_web/base.py`:

```python
def detect_design_source(self, project_path: Path) -> str:
    directives = self._load_directives(project_path)
    ext_path = directives.get("design_source_path")
    if ext_path:
        expanded = Path(ext_path).expanduser()
        if expanded.is_dir():
            return "v0-external"
        logger.warning("design_source_path %s not found", expanded)
    # Existing in-project detection
    if (project_path / "v0-export").is_dir():
        return "v0"
    return "none"
```

The core `_deploy_v0_export_to_worktree()` in dispatcher.py needs a small change: accept the source path as parameter instead of hardcoding `project_path / "v0-export"`. The profile provides the resolved path.

### D5: No git operations on external repo

The external design repo is treated as a read-only snapshot. No git pull, no branch detection, no merge. If the design evolves, the user updates it manually (or via set-designer) and the next dispatch picks up the changes via the symlink.

## Risks / Trade-offs

**[Risk] Symlink to external repo breaks if repo is moved** → The path is in orchestration.yaml — user updates it if they move the repo. Log an error at dispatch time if the path is gone.

**[Risk] Design token extraction regex is fragile** → shadcn/ui uses a highly predictable CSS variable format. We only extract `--variable: value` pairs from `:root` and `.dark` blocks. If format changes, extraction fails gracefully (empty design tokens section, log warning).

**[Risk] Design rules from external repo may conflict with project rules** → Prefix external design rules with `design-` in the rules directory to namespace them. The `_build_rule_injection` function's category matching handles the rest.

**[Trade-off] Symlink vs copy** → Symlink means agents see live changes to the design repo. Copy would snapshot. Symlink is correct — it matches the existing v0-export pattern and ensures agents always see the latest design state.
