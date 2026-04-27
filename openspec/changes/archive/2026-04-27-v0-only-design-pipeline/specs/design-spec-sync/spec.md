# Spec: Design Spec Sync (delta)

## REMOVED Requirements

### Requirement: REQ-SPEC-SYNC — Inject design references into spec files

**Reason:** `set-design-sync` is removed entirely (replaced by `set-design-import` for v0). Spec files no longer receive auto-injected `## Design Reference` blocks because design content is no longer a markdown spec — it is the v0-export TSX files referenced from each change's `design-source/` slice.

**Migration:** Existing spec files with `## Design Reference` blocks should have those blocks removed (they reference removed `design-system.md` sections that no longer exist). Future per-change design context comes from the dispatcher injecting a `## Design Source` section into `input.md` based on the v0 manifest.

### Requirement: REQ-SPEC-PRESERVE — Preserve existing spec content

**Reason:** No longer applicable — the tool that this requirement governed is removed.

**Migration:** None required.

### Requirement: REQ-SPEC-IDEMPOTENT — Running multiple times produces same result

**Reason:** No longer applicable — the tool that this requirement governed is removed.

**Migration:** Idempotent re-import is now the responsibility of `set-design-import` (see `v0-export-import` capability, "Idempotent re-import" requirement).
