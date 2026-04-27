# Proposal: Design Layer Separation

## Why

~3000 lines of web-specific design code (Figma MCP, CSS/Tailwind token parsing, shadcn/ui component detection, design-brief.md scope matching) live in the core layer (`lib/set_orch/` and `lib/design/`). This violates the Layer 1/Layer 2 architecture where core must remain project-type agnostic. Non-web project types (e.g., CLI tools, Python packages, mobile apps) should not carry Figma/Tailwind/shadcn dependencies. The design pipeline should flow through `ProjectType` ABC methods so modules can provide their own design integration (or none at all).

## What Changes

- Extract design bridge calls from `dispatcher.py`, `verifier.py`, and `planner.py` into `ProjectType` ABC methods
- Add 3 new ABC methods to `profile_types.py`: `build_per_change_design()`, `build_design_review_section()`, `fetch_design_data_model()`
- Move the bridge.sh call sites from core into `WebProjectType` overrides in `modules/web/`
- Keep `_fetch_design_context()` in planner.py (generic: reads any markdown file)
- Keep `lib/design/` files in place physically (they're tooling, not orchestration logic) but remove direct bridge.sh imports from core orchestration modules
- Remove hardcoded Next.js file references from `compare.py` (use existing `profile.get_comparison_template_files()`)

## Capabilities

### New Capabilities

- `design-profile-hooks`: ProjectType ABC methods for design integration

### Modified Capabilities

_(none — the design pipeline behavior is identical, only the call path changes)_

## Impact

- **Core (`lib/set_orch/`)**: `dispatcher.py`, `verifier.py`, `planner.py`, `profile_types.py` — extract bridge.sh calls into profile method calls
- **Module (`modules/web/`)**: `project_type.py` — implement the 3 new ABC methods with the existing bridge.sh logic
- **No behavioral change** — the design pipeline produces identical output, just routed through the profile system
- **Risk**: Medium — dispatcher and verifier are critical paths. Must validate with E2E run.
- **`lib/design/`**: Files stay in place. They're CLI tools (`set-design-sync`, `set-figma-fetch`) not core orchestration imports. The web module calls them via subprocess.
