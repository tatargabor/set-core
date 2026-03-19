# Design Tool Integration

## When `design-snapshot.md` exists (in shared runtime or project root):

1. You MUST read `design-snapshot.md` BEFORE implementing any UI component
2. Use the EXACT color, spacing, typography, and radius values from the Design Tokens section — do NOT fall back to shadcn/ui defaults if they differ from the design
3. Match the component hierarchy structure from the relevant frame in the Component Hierarchy section
4. If the design specifies `bg-blue-600` for buttons but your framework default is `bg-primary` (which maps to a different color), use `bg-blue-600` explicitly
5. Report design gaps — if you need a design spec that doesn't exist, note it as a `design_gap` in your output

## Orchestration pipeline integration

The design pipeline is automated — these happen without manual intervention:

- **Preflight:** if a design MCP (figma/penpot) is registered, the orchestrator fetches a `design-snapshot.md` before planning and copies it to project root for worktree agents
- **Planner:** `design_prompt_section()` injects design tokens + component hierarchy into the decompose prompt. Planner embeds specific token values (colors, sizes, frame names) in each change scope
- **Dispatch:** `design_context_for_dispatch()` extracts relevant Design Tokens + frame-matched Component Hierarchy from the snapshot and appends it to the agent's `proposal.md`
- **Verify gate:** `build_design_review_section()` adds a design compliance check to the code review prompt — token mismatches are reported as [WARNING], not [CRITICAL]

## When a design MCP server (figma, penpot, sketch, zeplin) is available but no snapshot exists:

1. You MUST query the design tool for specs BEFORE implementing UI elements: colors, spacing, typography, layout, component structure
2. Use design tokens from the tool rather than hardcoding values
3. Match component hierarchy from the design

## When neither design tools nor snapshot are available:

Ignore this rule entirely.
