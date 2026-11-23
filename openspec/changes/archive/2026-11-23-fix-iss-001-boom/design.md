## Context

`resolve_project_name()` in `lib/set_orch/paths.py` uses `git rev-parse --show-toplevel` to derive a project identifier from a path. When git fails (non-git directory, temp dir, scratchpad), the function returns the hardcoded string `"_global"`. All such directories share the single runtime at `~/.local/share/set-core/runtime/_global/`, including its sentinel directory.

`DetectionBridge._scan_project()` reads `sentinel/findings.json` for each supervised project. When two projects both resolve to `_global`, findings written by one (or left from a test) are visible to the other, causing spurious issue registration.

The `status-probe` scratchpad sits at a temp path outside any git repo. Its sentinel resolves to `_global`, which already contained a test finding `F001 "boom"`. The detector picked it up and created ISS-001.

## Goals / Non-Goals

**Goals:**
- Non-git directories get a stable, unique project name derived from their path rather than collapsing to `"_global"`.
- `DetectionBridge` skips findings that lack the minimum required fields (`summary` non-empty, `severity` present), logging a warning so operators can investigate.
- `"_global"` is kept as the explicit fallback only when no path is available at all.

**Non-Goals:**
- Migrating existing `_global` runtime data for projects that were previously under `_global`. (Old data stays; next scan uses the new name.)
- Changing the sentinel findings file format or adding server-side validation.
- Removing the `"_global"` runtime slot entirely.

## Decisions

### Decision 1 — Fallback name: directory basename vs hash

**Choice:** use the directory's basename (last path component).

**Alternatives considered:**
- *SHA-256 of the absolute path* — collision-free and stable, but opaque in logs and the runtime directory tree.
- *`_global` as today* — simplest, but causes cross-contamination.
- *Basename* — human-readable, works for scratchpads named after their purpose (e.g. `status-probe`). Risk of collision between two unrelated directories with the same name; accepted because (a) temp/scratchpad dirs have stable, purposeful names in practice, and (b) the collision only merges sentinel data — it does not corrupt orchestration state.

```python
# lib/set_orch/paths.py  resolve_project_name()
# OLD
return "_global"
# NEW
return os.path.basename(os.path.abspath(cwd)) or "_global"
```

### Decision 2 — DetectionBridge validation gate

**Choice:** skip findings where `summary` is empty or falsy, or where `severity` is absent. Log a WARNING with the finding id and project name.

**Rationale:** The sentinel-findings spec requires `summary`, `severity`, `change`, `discovered_at`, and `status` for every finding. A finding missing `summary` or `severity` is definitionally malformed. Skipping it (rather than raising) keeps the detector loop stable. The WARNING ensures operators can diagnose stale test data in the sentinel directory.

`change` and `discovered_at` are intentionally NOT gated — older findings written before these fields were required should still be actionable.

## Risks / Trade-offs

- **Basename collision** → two different directories with the same last component share a runtime. Mitigated by the fact that set-core is git-oriented; non-git use is exceptional.
- **Existing `_global` data is not migrated** → projects that currently resolve to `_global` will get a new runtime directory on the next start. Their old `_global` sentinel findings will no longer be scanned. This is acceptable: the old findings are test artifacts in known cases, and the change is additive (no deletion).

## Migration Plan

1. Deploy `resolve_project_name()` change. Non-git projects immediately use their basename as the runtime key on next start.
2. No data migration script needed: existing `_global` data is ignored going forward. Operators who want to preserve old sentinel findings for a project can manually move `~/.local/share/set-core/runtime/_global/sentinel/` to `runtime/<basename>/sentinel/`.
3. No rollback risk: the old `_global` directory is never deleted; reverting the code restores the previous behavior.

## Open Questions

- Should we emit a one-time log at INFO level when a project resolves to a basename-derived name (to aid first-run diagnostics)? Tentatively yes — add `logger.debug("Non-git project '%s' resolved to runtime key '%s'", cwd, name)`.
