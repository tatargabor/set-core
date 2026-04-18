# Spec: Design Snapshot (delta)

## REMOVED Requirements

### Requirement: Snapshot caching in state directory

**Reason:** `design-snapshot.md` is no longer the design artifact for orchestration. The framework consumes v0 React/TSX exports as the source of truth, not a markdown approximation. The Figma MCP fetcher and snapshot caching layer are removed entirely.

**Migration:** Existing projects with `design-snapshot.md` files may delete them. The replacement design context is the per-change `design-source/` slice populated by the web module from `v0-export/`. See the `v0-design-source` capability for details.

### Requirement: set-design-sync support for figma.md input

**Reason:** `set-design-sync` is removed in this change. The `figma.md` (Figma Make prompt) input format is no longer supported.

**Migration:** Scaffold authors describing pages historically via `figma.md` SHOULD instead author `docs/v0-prompts.md` (one prompt per page) and use them to generate v0 designs. The prompts file is then committed alongside `v0-export/` for audit trail.
