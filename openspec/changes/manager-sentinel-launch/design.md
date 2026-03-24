# Design: manager-sentinel-launch

## Context

The manager UI was built with placeholder sentinel/orchestrator controls. The sentinel Start button spawns `claude -p` with a 3-line hardcoded prompt that knows nothing about polling, crash recovery, checkpoint handling, or tier-based deference. Meanwhile, the actual sentinel logic lives in `.claude/commands/set/sentinel.md` — a 380-line skill file deployed to every consumer project via `set-project init`. The orchestrator Start button is redundant because the sentinel skill internally starts `set-orchestrate`.

The UI currently shows a flat tile grid with inline Start/Stop buttons. Production use requires navigating into a project to see docs, configure the spec path, and then launch — not one-click from a tile.

E2E test runs are currently bootstrapped manually (mkdir, copy docs, init, register). This needs to be a single `run.sh` command.

## Goals / Non-Goals

**Goals:**
- Sentinel launched from manager uses the same full skill logic as `/set:sentinel`
- UI navigates: tile overview → project detail → sentinel control with spec selection
- E2E bootstrap is a single script call
- Manager API is the single entry point for both manual (web UI) and automated (run.sh) launches

**Non-Goals:**
- Post-run result collection (`set-e2e-collect` — future change)
- Real-time sentinel log streaming in the web UI
- "New Project" wizard in the web UI (CLI is sufficient)
- Orchestration Gantt/token chart in project detail (existing dashboard handles this)

## Decisions

### D1: Skill file as prompt source

**Decision:** `supervisor.py` reads `.claude/commands/set/sentinel.md` from the project directory and uses it as `claude -p` prompt.

**Why not embed the skill in supervisor.py?** The skill is maintained as a deployable file in set-core's template system. Embedding creates divergence. Reading from the project dir means the deployed version is always what runs.

**Why not `claude -p "/set:sentinel"`?** Slash commands are interactive-mode features. `claude -p` treats the argument as a plain text prompt, not a command invocation.

**Fallback:** If the skill file doesn't exist (old project, not yet init'd), fall back to the current hardcoded prompt with a warning log.

**Max turns:** Increase from 200 to 500. The sentinel runs for hours — 200 turns is too low for a full orchestration run.

### D2: Remove orchestrator start/stop from API and UI

**Decision:** Remove `POST /api/projects/{name}/orchestration/start` and `stop` endpoints. Remove the Orchestrator row from the UI.

**Why:** The sentinel skill's Step 1 is `set-orchestrate start $ARGUMENTS &`. Having a separate orchestrator button invites confusion — users might start the orchestrator without a sentinel, or start both and get conflicts.

**Alternative considered:** Keep orchestrator-only mode for debugging. Rejected — for debugging, use `set-orchestrate` directly from CLI. The manager is for production workflows where sentinel always supervises.

**Backward compat:** The orchestrator PID tracking in `supervisor.py` stays (the sentinel starts it, health_check still monitors it). Only the API endpoints and UI buttons are removed.

### D3: Tile → detail navigation pattern

**Decision:** Project tiles on `/manager` become clickable links to `/manager/:project`. All controls (sentinel start, spec selection, issues) live in the detail view.

**Why:** Production flow is: look at project state → configure → launch. This is a multi-step interaction, not a one-click action. Tiles should show status at a glance.

**Route structure:**
- `/manager` — tile overview (existing, simplified)
- `/manager/:project` — new detail page
- `/manager/:project/issues` — existing issues page (already works)
- `/manager/:project/mutes` — existing mutes page (already works)

### D4: Spec path from docs listing

**Decision:** New API endpoint `GET /api/projects/{name}/docs` returns the docs directory tree. The UI shows a dropdown/autocomplete populated from top-level dirs under `docs/`.

**Why autocomplete, not file picker?** The planner decides which docs to use. The user just needs to point it at the right directory (`docs/`, `docs/v2/`, etc.). File-level selection is unnecessary — that's the planner's job.

**Implementation:** `os.walk()` on the project's `docs/` directory, limited to 2 levels depth, returning paths relative to project root.

### D5: E2E run.sh uses manager API

**Decision:** `run.sh` registers the project and starts sentinel via manager API calls, not direct `claude -p`.

**Why:** Single code path. The manager handles process lifecycle, crash recovery, and health monitoring. The web dashboard shows the run in real-time. If the manager isn't running, `run.sh` exits with an error.

**Alternative considered:** Direct `claude -p` as fallback when manager isn't running. Rejected — keep it simple. The manager should be running if you want to monitor via web dashboard.

## Risks / Trade-offs

- **[Risk] Skill file size as prompt** — The 380-line skill file is large for a `claude -p` prompt. → Mitigation: `claude -p` handles long prompts fine. The skill is designed to be self-contained.
- **[Risk] Removing orchestrator API breaks existing scripts** → Mitigation: No known consumers use the orchestrator API directly. E2E scripts will use the new sentinel API.
- **[Risk] `run.sh` requires running manager** → Mitigation: `run.sh` checks manager health before proceeding, with a clear error message.

## Open Questions

- None — all major decisions resolved during explore session.
