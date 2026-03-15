## Context

E2E run #13 showed two recurring waste patterns:
- Prisma client not generated in worktrees → every web change fails first build, agent self-heals (~2-5 min waste per change)
- Playwright browsers not installed → E2E tests fail until agent runs install manually
- WATCHDOG_HEARTBEAT is 71% of events.jsonl (75/106 events in run #13) — noise drowns real events

The web profile system (`wt-project-web`) already handles `bootstrap_worktree()` with `pnpm install`, but has no post-install hooks. The heartbeat emit happens in `engine.py` monitor loop on every poll cycle.

## Goals / Non-Goals

**Goals:**
- Eliminate "prisma generate" as a recurring agent self-heal task
- Eliminate "playwright install chromium" as a recurring agent task
- Reduce heartbeat noise in events.jsonl to ~5% of events (from 71%)

**Non-Goals:**
- Changing heartbeat frequency for internal liveness logic (stays every poll)
- Adding post-install hooks for non-web project types
- Making post-install hooks configurable per-project (hardcoded detection is sufficient)

## Decisions

### 1. Post-install hooks in WebProjectType.bootstrap_worktree()

Add two conditional steps after `pnpm install` succeeds:

```python
# After pnpm install succeeds:
# 1. Prisma generate if schema exists
if (Path(wt_path) / "prisma" / "schema.prisma").is_file():
    subprocess.run(["npx", "prisma", "generate"], cwd=wt_path, timeout=60, capture_output=True)

# 2. Playwright install if in devDependencies
pkg = json.loads((Path(wt_path) / "package.json").read_text())
if "@playwright/test" in pkg.get("devDependencies", {}):
    subprocess.run(["npx", "playwright", "install", "chromium"], cwd=wt_path, timeout=120, capture_output=True)
```

Each step is non-fatal — logged on failure but doesn't block bootstrap. Order: install → prisma → playwright.

**Why not profile.post_bootstrap_commands()?** Unnecessary abstraction. The detection logic is simple and web-specific. If other project types need post-install hooks, the pattern is clear to replicate.

### 2. Heartbeat throttle via poll counter modulo

In `engine.py` monitor loop, emit heartbeat only every 20th poll cycle:

```python
# Every poll cycle: internal heartbeat logic runs (unchanged)
# Every 20th poll cycle: emit event
if poll_count % 20 == 0:
    event_bus.emit("WATCHDOG_HEARTBEAT")
```

This reduces heartbeat events from ~240/hour to ~12/hour while keeping internal liveness at full frequency.

**Why 20 cycles?** At ~15s per cycle, 20 cycles ≈ 5 minutes. Frequent enough for post-mortem analysis, rare enough to not dominate the log.

## Risks / Trade-offs

- **Prisma generate timeout**: 60s should be plenty (typically <5s). If it hangs, the timeout kills it and bootstrap continues.
- **Playwright install size**: `chromium` download is ~130MB. On slow connections this could exceed 120s timeout. Non-fatal, agent can still self-heal.
- **Heartbeat gap in logs**: 5-minute gaps between heartbeats in events.jsonl. Sentinel doesn't use events for liveness (uses PID + state mtime), so no impact on stuck detection. Post-mortem analysis might miss exact crash timing, but state file timestamps cover this.
