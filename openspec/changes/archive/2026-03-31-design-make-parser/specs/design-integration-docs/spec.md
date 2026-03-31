# Spec: Design Integration Documentation

## Status: new

## Requirements

### REQ-DOCS-GUIDE: Create design integration guide
- Create `docs/guide/design-integration.md` covering:
  - Why design context matters (agents use shadcn defaults without explicit tokens)
  - Supported design sources (Figma Make .make files, manual design-system.md)
  - Step-by-step: create design in Figma Make → export .make → run set-design-sync → verify specs → start sentinel
  - What design-system.md contains (tokens, components, page layouts)
  - How design references appear in specs (## Design Reference sections)
  - How to update design (re-export .make, re-run set-design-sync)
  - Troubleshooting: agent ignoring design → check dispatch context, verify tokens in spec

### REQ-DOCS-ORCHESTRATION: Add pre-run checklist to orchestration guide
- Add "## Pre-Run Checklist" section to `docs/guide/orchestration.md`
- Checklist items: spec quality review, design sync (if Figma design exists), config review, project health audit
- Emphasize: spec quality directly determines output quality — vague specs produce generic results

### REQ-DOCS-SENTINEL: Add spec quality section to sentinel guide
- Add "## Spec Quality Prerequisites" section to `docs/guide/sentinel.md`
- Content: what makes a good spec for sentinel (concrete details, design tokens, page layouts, not just feature descriptions)
- Link to design integration guide for design-aware specs
- Warning: "Running sentinel with a vague spec and no design context will produce a working but visually generic app"
