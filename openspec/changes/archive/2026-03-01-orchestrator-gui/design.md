## Context

The wt-control GUI is a PySide6 frameless, always-on-top dashboard. It displays worktrees in a single QTableWidget with project header rows containing feature badges (`[M]` for memory, `[O]` for OpenSpec). Background QThread workers (StatusWorker, UsageWorker, TeamWorker, ChatWorker, FeatureWorker) poll data and emit signals to the UI thread. The ControlCenter class uses four mixins: TableMixin, HandlersMixin, MenusMixin, TeamMixin.

The `set-orchestrate` CLI writes `orchestration-state.json` at the project root. This file contains the full plan: per-change status (pending/dispatched/running/paused/done/merged/failed/merge-blocked), dependency graph, merge queue, checkpoint history, token usage, and gate metrics (test/review/verify/build timing). Per-worktree Ralph status comes from `.claude/loop-state.json` (already read by the GUI).

Since the orchestrator-layer change, several improvements landed: spec-driven orchestration, verify gate with retry, quality gates (worktree bootstrap, build verify, scope overlap detection), and memory integration. The GUI needs to reflect this full current state.

## Goals / Non-Goals

**Goals:**
- Live orchestrator status visible in wt-control without terminal access
- One-click checkpoint approval from the GUI
- Visual dependency graph showing change relationships and progress
- Per-change detail: status, iterations, tokens, gate results
- Follow existing GUI patterns (dialog-based, FeatureWorker polling, color profiles)

**Non-Goals:**
- Starting/stopping orchestration from GUI (use `set-orchestrate start/pause/resume` CLI)
- Editing the project brief from GUI
- Replanning from GUI (`set-orchestrate replan` stays CLI-only)
- Real-time streaming logs (use "View Log" to open the file)

## Decisions

### D1: Dialog-based orchestrator view (not embedded panel)

The orchestrator detail view is a new `OrchestratorDialog` (modeless QDialog), opened from the project header badge. This follows the MemoryBrowseDialog pattern.

**Why not a tab or embedded section?** The main window has no tab system — adding one would be a larger architectural change. A dialog can be resized independently and doesn't affect the compact main window layout. The badge provides at-a-glance status; the dialog provides depth.

**Why modeless (not modal)?** The developer should be able to keep the dialog open while the orchestrator runs, watching progress update. Modal would block interaction with the main window.

### D2: Extend FeatureWorker for orchestration state polling

Add orchestration-state.json reading to the existing FeatureWorker (polls every 15s). The FeatureWorker already reads per-project set-memory and wt-openspec status. Adding orchestration state is a natural extension.

The FeatureWorker emits `features_updated(dict)` — the dict gains a new `orchestration` key per project containing the parsed state (or `None` if no orchestration-state.json exists).

**Why not a new OrchestratorWorker?** One more QThread and signal adds complexity. The orchestration-state.json is a small file (5-20KB), reading it every 15s alongside existing polls is negligible. The FeatureWorker already has the per-project iteration loop.

### D3: Badge in project header row

A `[⚙]` badge appears on project header rows when `orchestration-state.json` exists. Badge colors follow the same profile-aware color system:

| Orchestrator Status | Badge Color | Text |
|---|---|---|
| running | green | ⚙ |
| checkpoint | yellow (blink) | ⚙ |
| paused | gray | ⚙ |
| stopped | gray dim | ⚙ |
| done | blue | ⚙ |
| failed (any change) | red | ⚙ |

Click → open OrchestratorDialog. Tooltip → one-line summary: "Orchestrating: 3/7 done, 2 running, checkpoint waiting".

### D4: OrchestratorDialog layout

```
┌─ Orchestrator: project-name ──────────────────────────┐
│                                                        │
│  Status: ● running  Plan v2  3/7 changes done          │
│  Tokens: 145,230   Elapsed: 1h 23m                     │
│                                                        │
│  ┌─ Dependency Graph ──────────────────────────────┐   │
│  │                                                  │   │
│  │   [add-user-model] ──▶ [add-auth-middleware]     │   │
│  │          ✓ merged            ● running            │   │
│  │                                                  │   │
│  │   [add-api-routes] ──▶ [add-frontend-auth]       │   │
│  │       ● running           ○ pending               │   │
│  │                                                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                        │
│  ┌─ Changes ───────────────────────────────────────┐   │
│  │ Name              Status   Iter  Tokens  Gates  │   │
│  │ add-user-model    ✓ merged  8/30  12340   3.2s  │   │
│  │ add-auth-middle   ● run     5/30  8921    -     │   │
│  │ add-api-routes    ● run     3/30  4210    -     │   │
│  │ add-frontend-a    ○ pend    -     -       -     │   │
│  │ ...                                              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                        │
│  [Approve Checkpoint]  [View Log]  [Close]             │
└────────────────────────────────────────────────────────┘
```

Three sections:
1. **Header bar**: Overall status, plan version, progress ratio, token total, elapsed time
2. **Dependency graph**: Custom QPainter widget rendering the change DAG
3. **Change table**: QTableWidget with per-change details

Bottom buttons: Approve (only enabled at checkpoint), View Log, Close.

### D5: Dependency graph widget (DAGWidget)

A custom QWidget using QPainter to render the change dependency graph. Uses a simple left-to-right layered layout:

1. Topological sort changes into layers (layer 0 = no dependencies, layer 1 = depends on layer 0, etc.)
2. Each layer is a vertical column of change nodes
3. Edges drawn as lines/arrows between dependent nodes
4. Node color reflects status (same palette as badge)

Node rendering: rounded rectangle with change name (truncated to 20 chars) and status icon. Tooltip on hover shows full name + status details.

**Why QPainter, not a graph library?** The DAG is small (typically 3-15 nodes). QPainter keeps it dependency-free and follows the DualStripeBar custom widget pattern already in the codebase.

### D6: Checkpoint approval via state file

The approve button writes to `orchestration-state.json` exactly as `set-orchestrate approve` does:

```python
# Read current state
state = json.load(f)
# Find latest checkpoint, mark approved
state['checkpoints'][-1]['approved'] = True
state['checkpoints'][-1]['approved_at'] = datetime.now().isoformat()
# Write back
json.dump(state, f)
```

The orchestrator's approval poll loop (every 5s) picks this up. No IPC needed — file-based coordination, same as Ralph loop stop.

### D7: Color profile integration

All orchestrator colors are added to each color profile in `constants.py`:

```python
"orch_running": "#2ecc71",
"orch_checkpoint": "#f1c40f",
"orch_paused": "#95a5a6",
"orch_done": "#3498db",
"orch_failed": "#e74c3c",
"orch_pending": "#7f8c8d",
"orch_merged": "#27ae60",
"orch_badge_bg": "#2c3e50",
```

Each profile (light, dark, gray, high_contrast) gets appropriate values.

### D8: Gate results display

The change table includes a "Gates" column showing aggregate gate timing from `gate_test_ms`, `gate_review_ms`, `gate_verify_ms`, `gate_build_ms` fields in orchestration-state.json. Tooltip breaks down individual gate timings and retry count.

## Risks / Trade-offs

**[File contention]** GUI writes approval to orchestration-state.json while orchestrator is reading/writing it.
→ Mitigation: Atomic write (write to temp file + rename). The orchestrator already uses this pattern via jq + mv. GUI uses the same approach.

**[Stale data]** 15s FeatureWorker poll means up to 15s delay in status updates.
→ Mitigation: Acceptable for a monitoring view. The dialog can optionally have a "Refresh" button that calls `FeatureWorker.refresh_now()` (existing mechanism).

**[Large plans]** Plans with 20+ changes may make the DAG hard to read.
→ Mitigation: The DAG widget supports scrolling. Node truncation keeps it compact. This is an edge case — typical plans have 3-10 changes.
