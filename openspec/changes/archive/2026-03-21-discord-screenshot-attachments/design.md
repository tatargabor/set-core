# Design: Discord Screenshot Attachments

## Goals / Non-Goals

**Goals:**
- Visual test feedback in Discord without leaving the channel
- Spoiler-tagged inline screenshots for failures (non-intrusive)
- Compact gallery for run completion summary
- Respect Discord API limits (25MB, 10 files per message)

**Non-Goals:**
- Screenshot diffing or visual regression
- Permanent screenshot archival in Discord
- Video attachments

## Decisions

### D1: New module `discord/screenshots.py`

**Decision:** Create a dedicated module for screenshot Discord operations. Keeps file I/O and Discord attachment logic separate from event routing.

```python
# lib/set_orch/discord/screenshots.py

async def post_smoke_screenshots(thread, change_name: str, spoiler: bool = True) -> int:
    """Post smoke test screenshots for a change to a Discord thread."""

async def post_e2e_screenshots(thread, cycle: int | str) -> int:
    """Post E2E screenshots for a cycle to a Discord thread."""

async def post_screenshot_gallery(thread, run_screenshots: list[Path]) -> int:
    """Post all screenshots as a gallery message at run completion."""
```

### D2: Discord file attachment via `discord.File`

**Decision:** Use `discord.File(fp, filename, spoiler)` for each image. Spoiler parameter wraps the image — users click to reveal.

```python
import discord
files = [discord.File(path, filename=path.name, spoiler=True) for path in screenshots]
await thread.send(content="📸 Smoke screenshots:", files=files[:10])
```

### D3: Image preparation before upload

**Decision:** Before uploading, check file sizes. If any image exceeds 1MB, resize using Pillow (optional dependency). If Pillow is not installed, skip oversized images with a warning.

```python
MAX_IMAGE_SIZE = 1_000_000  # 1MB
MAX_FILES_PER_MSG = 10
MAX_TOTAL_SIZE = 25_000_000  # 25MB Discord limit

def _prepare_screenshots(paths: list[Path]) -> list[Path]:
    """Filter and optionally resize screenshots for Discord upload."""
```

### D4: Integration points in the event flow

**Decision:** Hook into existing event flow at three points:

1. **Smoke failure** — `_handle_state_change` when `change_status → verify-failed` and screenshots exist
2. **E2E completion** — `_handle_event` on `E2E_COMPLETE` event (emitted by verifier)
3. **Run completion** — `_handle_run_complete` collects all screenshots and posts gallery

### D5: Screenshot discovery via `SetRuntime` paths

**Decision:** Use existing `SetRuntime().smoke_screenshots_dir(change_name)` and `SetRuntime().e2e_screenshots_dir(cycle)` to find screenshots. No new path conventions.

```python
from ..paths import SetRuntime
rt = SetRuntime()
smoke_dir = rt.smoke_screenshots_dir(change_name)
e2e_dir = rt.e2e_screenshots_dir(cycle)
screenshots = list(Path(smoke_dir).glob("**/*.png"))
```

### D6: Data source — state file, not event bus

**Decision:** The watcher polls the state JSON file, NOT the orchestrator's in-process event bus. Screenshot data is already in the state file per change:

```json
{
  "smoke_screenshot_dir": "wt/orchestration/screenshots/smoke/auth-system",
  "smoke_screenshot_count": 3,
  "e2e_screenshot_dir": "wt/orchestration/e2e-screenshots/cycle-1",
  "e2e_screenshot_count": 5
}
```

The watcher detects per-change status transitions. When it sees:
- `status → verify-failed` + `smoke_screenshot_count > 0` → post smoke screenshots
- `status → merged/done` + `e2e_screenshot_count > 0` → post e2e screenshots (if phase-end just ran)

For the run completion gallery, gather all `smoke_screenshot_dir` and `e2e_screenshot_dir` from all changes in the state.

**Why not event bus:** The event bus is in-process to the orchestrator. The set-web process (where the Discord bot runs) is a separate process that only sees state file changes.

## Architecture

```
Orchestrator process              set-web process
━━━━━━━━━━━━━━━━━━━━              ━━━━━━━━━━━━━━━━
verifier runs smoke                  │
  └─ collect_screenshots()           │
  └─ write state.json ──────────────►│ watcher polls
       smoke_screenshot_dir: "..."   │   ↓
       smoke_screenshot_count: 3     │ _forward_to_discord()
       status: verify-failed         │   ↓ detects status change
                                     │ post_screenshots(spoiler=True)
                                     │
verifier runs E2E                    │
  └─ collect to e2e-dir              │
  └─ write state.json ──────────────►│ watcher polls
       e2e_screenshot_dir: "..."     │   ↓
       e2e_screenshot_count: 5       │ post_screenshots()
                                     │
orchestrator sets done ─────────────►│ watcher polls
                                     │   ↓ status → done
                                     │ collect_run_screenshots()
                                     │ post_screenshot_gallery()
```
