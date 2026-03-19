## Why

E2E Run 16 shows that agents produce structurally correct code (all gates pass) but the implementation diverges significantly from the Figma design — wrong component patterns, missing icons, incorrect layout structures, seed data names not matching design mockData. Root cause: the design bridge only injects **Design Tokens** (color/spacing counts) into agent context, never the **actual Figma source files** that contain component code, data models, and UI structure. Agents have no way to know that the cart should have product thumbnails, that the navbar uses a ShoppingBag icon, or that products have a `shortDescription` field.

## What Changes

- **set-core `lib/design/bridge.sh`**: New function `design_sources_for_dispatch()` — finds `docs/figma-raw/*/sources/` files, matches them against change scope keywords, returns relevant source file contents for injection into agent proposals
- **set-core `lib/set_orch/dispatcher.py`**: Call the new bridge function and append matched Figma source files to proposal context alongside tokens
- **set-core `lib/set_orch/templates.py`**: Planner instructions enhanced — when Figma sources exist, extract data model names/fields and embed them in scope descriptions
- **set-core `lib/design/bridge.sh` `build_design_review_section()`**: Include component structure checks (not just token matching) — missing icons, missing images, wrong layout pattern flagged as WARNING
- **set-project-web `design-integration.md`**: New rule — when `docs/figma-raw/*/sources/` exists, agents MUST read matched source files before implementing UI; source files are the ground-truth for component structure, model fields, icon usage, and layout patterns
- **set-project-web `ui-conventions.md`**: Clarify that when design source files show specific icons (e.g., `ShoppingBag` for cart), agents must use those exact icons, not generic text

## Capabilities

### New Capabilities
- `figma-source-dispatch`: Design bridge extracts and injects relevant Figma source files (component code, mockData, layout patterns) into agent dispatch context — agents see actual component structure, not just token statistics
- `design-model-extraction`: Planner extracts data model fields and entity names from Figma sources (e.g., mockData.ts) and embeds them in change scope descriptions — ensures seed data, schema fields, and UI labels match the design

### Modified Capabilities
- `design-dispatch-injection`: Dispatch context now includes matched Figma source file contents alongside Design Tokens
- `design-verify-gate`: Review section includes component-structure checks (icons, images, layout pattern), not just token color matching

## Impact

- **set-core**: `lib/design/bridge.sh`, `lib/set_orch/dispatcher.py`, `lib/set_orch/templates.py`, `lib/set_orch/verifier.py`
- **set-project-web**: `templates/nextjs/rules/design-integration.md`, `templates/nextjs/rules/ui-conventions.md`
- **Consumer projects**: After `set-project init`, agents will receive Figma source file context and follow design structure more accurately
- No breaking changes — purely additive context injection
