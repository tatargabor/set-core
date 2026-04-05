# Design: comprehensive-logging-and-e2e-fixes

## Core Principle

**Every return must explain itself. Every fallback must announce itself. Every path must be visible.**

## Log Level Policy

| Level | When | Default |
|-------|------|---------|
| DEBUG | Normal empty returns, expected skips, path resolution | **ON** (default level = DEBUG) |
| INFO | Pipeline milestones, gate entry/exit, successful operations | ON |
| WARNING | Fallbacks triggered, unexpected empty data, skipped checks | ON |
| ERROR | Data loss, unrecoverable failures | ON |
| `[ANOMALY]` prefix | Should-never-happen conditions | WARNING level, sentinel-scannable |

**Config override:** `orchestration.yaml` → `log_level: INFO` to suppress DEBUG in production.

## Design Decisions

### 1. DEBUG as default level (not INFO)

**Decision:** Set root logger level to DEBUG for orchestration modules.

**Why:** The whole point of this change is visibility. INFO hides the "why did this return empty" breadcrumbs that are essential for post-mortem debugging. Users who find it too verbose can set `log_level: INFO` in config.

### 2. SetRuntime elimination pattern

**Decision:** Replace `SetRuntime().X` with `_resolve_path(state_file, relative)` everywhere.

```python
# BEFORE (broken):
_digest_dir = SetRuntime().digest_dir

# AFTER (correct):
_digest_dir = os.path.join(os.path.dirname(state_file), "set", "orchestration", "digest")
```

**Why:** SetRuntime() resolves paths relative to CWD or a global config, not relative to the actual project. In multi-project environments (E2E runs), it points to the wrong project's directories.

### 3. Own spec detection via filesystem comparison

**Decision:** Replace git merge-base diff with `git ls-tree main` vs `os.listdir()`.

```
main has:       [navigation.spec.ts]
worktree has:   [navigation.spec.ts, blog.spec.ts]
own =           [blog.spec.ts]
```

**Why:** Git merge-base is trivial post-integration-merge (HEAD ≈ main). Filesystem comparison works regardless of merge state. Falls back to git log for modified (not just added) specs.

### 4. Gate executor logging pattern

**Decision:** Every gate logs entry with all inputs and exit with result + timing.

```
Gate[build] START change=blog-pages wt=/path/to/wt cmd="pnpm run build"
Gate[build] END change=blog-pages result=pass elapsed=8015ms
```

**Why:** When a gate fails and we investigate, the first question is "what command ran, where, and what happened?" Currently none of this is in the logs.

### 5. Manifest validation at agent completion

**Decision:** In `handle_change_done()`, scan worktree for actual spec files and update e2e-manifest.json.

**Why:** Manifest is written at dispatch with predicted names. Agent may name files differently. Validating at completion ensures the manifest matches reality before gates use it.

## Files to Modify

| File | Changes | Log Points |
|------|---------|------------|
| `dispatcher.py` | DEBUG for all return paths, path logging | ~30 |
| `merger.py` | SetRuntime fix, own-spec rewrite, gate logging, load_profile paths | ~25 |
| `engine.py` | SetRuntime fix, digest_dir logging, recovery logging | ~15 |
| `verifier.py` | Gate executor entry/exit, handle_change_done manifest update, except upgrades | ~20 |
| `profile_loader.py` | Path resolution logging (already partially done) | ~3 |
| `planner.py` | Validation logging, test plan injection | ~5 |
| `state.py` | Lock acquisition logging (already done by other agent) | ~2 |
| `bin/set-orchestrate` | Bash decision point logging | ~5 |
| `bin/set-merge` | Bash merge step logging | ~5 |
| `templates/core/rules/set-sentinel-autonomy.md` | Log scanning directive | text |
