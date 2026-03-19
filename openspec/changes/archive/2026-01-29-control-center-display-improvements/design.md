## Context

The Control Center GUI currently shows all worktrees and the status display is not optimal:
- "waiting" is misleading (Claude is working, not waiting)
- PID is not useful information for the user
- There's no way to filter the list

The `wt-focus` script already contains editor window detection logic that we can reuse.

## Goals / Non-Goals

**Goals:**
- Quickly find actively used worktrees
- More understandable status display
- See which skill is currently running

**Non-Goals:**
- Skill modification for 3rd party skills (only modifying our own skills)
- Complex filter UI (dropdown, multi-filter) - just a simple toggle
- Status history/logging

## Decisions

### 1. Editor detection in the GUI (not in wt-status)

**Decision:** Editor window detection happens in the GUI layer, not in wt-status.

**Rationale:**
- Only runs when the filter is active (doesn't slow down polling)
- The GUI already uses xdotool (Focus Window)
- Simpler caching per render cycle

**Alternative:** Extending wt-status with `editor_open: true/false` field
- Rejected because: Would run on every poll, slowing down status refresh

### 2. Skill tracking with timestamp-based status file

**Decision:** Skills write to `.set-core/current_skill` file in `name|timestamp` format.

**Rationale:**
- Simple to implement
- No "cleanup" logic needed - old entries automatically expire (30 minutes)
- Skills only write at startup, no need to "delete at end"

**Alternative:** Session JSONL parsing
- Rejected because: Complex, slow, fragile (JSONL structure may change)

### 3. Filter button icon: 🖥️

**Decision:** The filter button uses the 🖥️ (monitor) icon.

**Rationale:**
- Visually suggests the "editor window" concept
- Clear toggle (active/inactive state indicated by color)

## Risks / Trade-offs

**[Risk] xdotool not available on every Linux distribution**
→ Mitigation: Editor detection gracefully fails, filter simply doesn't work (no crash)

**[Risk] Editor window title doesn't always contain the folder name**
→ Mitigation: Fallback to window class based search, best-effort matching

**[Risk] Skill status file may become stale if skill crashes**
→ Mitigation: Ignored after 30 minute timeout

**[Trade-off] PID removal**
→ May be useful for debugging, but most users don't need it. Advanced users can use `wt-status --json`.
