## Context

The `improve-memory-hooks` change created `wt-hook-memory-save` and `wt-hook-memory-recall` as standalone bash scripts. They're symlinked to `~/.local/bin` by `install.sh` and self-degrade gracefully (exit 0 if `set-memory` not available). However, `wt-deploy-hooks` — the script that writes `.claude/settings.json` for projects — only deploys `wt-hook-skill` and `wt-hook-stop`. The memory hooks were never added to its template.

The benchmark `init-with-memory.sh` works around this by manually appending memory hooks via jq after `wt-deploy-hooks` runs.

## Goals / Non-Goals

**Goals:**
- Memory hooks deployed by default to all projects via `wt-deploy-hooks`
- Existing projects upgraded when `wt-deploy-hooks` re-runs (add missing memory hooks)
- Benchmark baseline can opt out with `--no-memory` flag
- Documentation reflects the automatic hooks architecture

**Non-Goals:**
- Changing hook behavior (save/recall logic stays the same)
- Adding new hooks beyond the existing two
- Changing the OpenSpec skill-level memory hooks (`set-memory-hooks install`)

## Decisions

### Deploy memory hooks by default
**Choice**: Include memory hooks in the default `wt-deploy-hooks` config alongside `wt-hook-skill` and `wt-hook-stop`. Both hooks self-degrade (exit 0) when `set-memory` is unavailable, so there's zero impact on projects without shodh-memory installed.

**Alternative**: Opt-in flag (`--with-memory`). Rejected because it requires every caller to know about memory hooks, and the graceful degradation makes opt-in unnecessary.

### Add `--no-memory` flag for baseline
**Choice**: `wt-deploy-hooks --no-memory <dir>` skips memory hooks. Used by benchmark `init-baseline.sh` to ensure clean baseline runs.

### Upgrade existing configs
**Choice**: When `wt-deploy-hooks` finds a settings.json with Stop/UserPromptSubmit hooks but without memory hooks, it appends the memory hooks to the existing arrays rather than skipping entirely. This handles the upgrade path for projects deployed before this change.

## Risks / Trade-offs

- **[Risk] Existing projects get unexpected hooks on re-deploy** → Hooks are no-op without shodh-memory; timeout 15-30s is generous but hooks exit in <100ms when set-memory is absent.
- **[Risk] Memory recall adds latency to every prompt** → `wt-hook-memory-recall` has 15s timeout but typically completes in <1s. If shodh-memory is slow/broken, it exits 0 early.
