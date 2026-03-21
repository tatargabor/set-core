---
paths:
  - "src/components/**"
  - "src/pages/**"
  - "src/views/**"
---
# Design Integration

These rules apply when a design MCP (e.g., Figma) is registered. If no design tool is available, skip this file — agents self-gate.

## Before Implementing UI

- Query the design tool for the relevant frame/page before writing component code
- If the required frame is MISSING from the design, flag it as a `design_gap` ambiguity — do not guess layout or styling

## Design Token Mapping

- Extract design tokens (colors, spacing, typography, shadows) from the design tool
- Map tokens to your project's token system (CSS custom properties, theme config, or style constants)
- Token files are the source of truth — never hardcode color values, spacing, or font sizes in components
- When adding new tokens, follow the existing naming convention in the project's token files

## Component Mapping

- Map design components to existing component library equivalents where possible
- Reuse existing components before creating custom ones
- Match design states (hover, focus, disabled, error) to component props or variants
- Maintain naming consistency between design file component names and code component names

## Responsive Behavior

- Check design for breakpoint-specific frames (mobile, tablet, desktop)
- Implement mobile-first, then enhance for larger breakpoints
- If only one breakpoint is designed, flag missing breakpoints as `design_gap`
