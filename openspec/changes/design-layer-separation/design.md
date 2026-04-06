# Design: Design Layer Separation

## Context

The core orchestration modules (`dispatcher.py`, `verifier.py`, `planner.py`) directly call `lib/design/bridge.sh` functions via subprocess. This couples core to web-specific design tooling. The call chain analysis shows 6 bridge.sh call sites across 3 core modules:

| Module | bridge.sh function | Purpose |
|--------|-------------------|---------|
| dispatcher.py:186 | `design_brief_for_dispatch()` | Scope-match pages from design-brief.md |
| dispatcher.py:199 | `design_context_for_dispatch()` | Extract design tokens |
| dispatcher.py:1805 | `design_context_for_dispatch()` | Inline design context for dispatch prompt |
| dispatcher.py:1814 | `design_sources_for_dispatch()` | Figma component source code |
| verifier.py:1227 | `build_design_review_section()` | Design compliance for code review |
| planner.py:1839 | `design_data_model_section()` | TypeScript interfaces from Figma |

Additionally, `compare.py` hardcodes `"src/app/globals.css"`, `"next.config.js"`, `"postcss.config.mjs"`.

The profile system already has one design hook (`design_page_aliases()`) but no module overrides it.

## Goals

- All bridge.sh calls flow through `ProfileType` ABC methods
- Core modules never import or subprocess-call bridge.sh directly
- Identical runtime behavior (same design.md output, same review sections)
- Non-web project types get no-op defaults (empty string returns)

## Non-Goals

- Moving `lib/design/` files to `modules/web/` (they're CLI tools, not imports)
- Changing bridge.sh function implementations
- Adding new design features

## Decisions

### 1. Three new ABC methods on ProjectType
**Choice**: Add `build_per_change_design()`, `get_design_dispatch_context()`, `build_design_review_section()`, `fetch_design_data_model()` to `ProjectType` ABC.
**Why**: Each maps cleanly to a bridge.sh call cluster. The base class returns no-op defaults (False/empty string). Only web module overrides them.
**Alternative**: Single `design_hook(action, **kwargs)` dispatch — rejected because it's untyped and harder to document.

### 2. WebProjectType calls bridge.sh via subprocess (unchanged)
**Choice**: The web module's implementations call bridge.sh exactly as the core does today — `run_command(["bash", "-c", f'source bridge.sh && function ...'])`.
**Why**: bridge.sh is a proven, tested shell script. Rewriting in Python adds risk. The subprocess pattern is established and works.
**Alternative**: Rewrite bridge.sh in Python — too large (1028 lines), too risky for this change.

### 3. Keep `_fetch_design_context()` in planner.py
**Choice**: The planner's design context fetching (searching for markdown files) stays in core.
**Why**: It's generic — it reads any markdown file by name. Not web-specific. No bridge.sh involved.

### 4. Profile receives bridge_path from core
**Choice**: Core passes `SET_TOOLS_ROOT` (or bridge.sh path) to profile methods so the web module knows where to find bridge.sh.
**Why**: The web module shouldn't hardcode `SET_TOOLS_ROOT`. Core already resolves it.
**Alternative**: Web module resolves bridge.sh path itself — fragile, duplicates logic.

### 5. compare.py uses existing profile method
**Choice**: Replace hardcoded file list with `profile.get_comparison_template_files()` which already exists.
**Why**: Zero new interface needed — just use what's there.

## Risks / Trade-offs

- **[Risk] Dispatch regression** → The dispatcher is the most critical path. Must validate that per-change design.md content is byte-identical before/after. Mitigated by running E2E with craftbrew scaffold (has full design pipeline).
- **[Risk] Profile loading order** → Profile must be loaded before dispatcher calls design methods. This is already guaranteed by the engine's init sequence.
- **[Risk] bridge.sh path resolution** → Web module needs to find `lib/design/bridge.sh`. Pass via `SET_TOOLS_ROOT` environment variable (already set globally by engine.py).

## Open Questions

None — the call chain analysis is complete and all interfaces are well-defined.
