## Why

Some projects keep their design assets (v0-export, design tokens, component library) in a separate repository or directory outside the project root. The consumer-app project uses `~/projects/consumer-app-design` for its design system while the code lives at `~/code/consumer-app`. The current design pipeline assumes v0-export lives inside the project — `detect_design_source()` and the dispatcher's symlink logic only look within the project directory. External design repos need explicit path configuration and adapted mount logic.

## What Changes

- Support `design_source_path` in `orchestration.yaml` — an absolute or relative path to an external design directory
- Adapt `profile.detect_design_source()` to check external path first, then fall back to in-project detection
- Adapt dispatcher's design symlink logic to mount external design repo into worktrees
- Extract design tokens from external repo's `globals.css` (CSS custom properties / `@theme` block) into a `design-system.md` for agent consumption
- Load `.set-designer/design-rules/*.md` from the external repo and inject as agent rules

## Capabilities

### New Capabilities
- `external-design-source`: Configure and mount design assets from an external directory into the orchestration pipeline — path resolution, worktree symlink, token extraction, design rule injection

### Modified Capabilities
- `design-bridge`: Extend design source detection to support external paths via `design_source_path` directive
- `orchestration-config`: Add `design_source_path` directive

## Impact

- `lib/set_orch/dispatcher.py` — adapt design symlink and context injection (~30 lines)
- `lib/set_orch/config.py` — add design_source_path directive
- `modules/web/set_project_web/base.py` — adapt `detect_design_source()` and `get_design_dispatch_context()` to check external path
- Consumer projects set `design_source_path` in orchestration.yaml
