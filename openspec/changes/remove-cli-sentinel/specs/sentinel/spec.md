# Sentinel — Delta Spec (remove-cli-sentinel)

## REMOVED Requirements

### Requirement: CLI bash supervisor
The `set-sentinel` CLI bash script SHALL be removed. Users SHALL use either the `/set:sentinel` Claude skill (via web UI) or `set-orchestrate start` directly.

**Reason:** The bash script duplicates orchestrator functionality without intelligent decision-making. The Claude skill provides superior crash recovery, stall detection, and bug fixing (Tier 1-3 authority). The bash script misleads users into expecting sentinel-level supervision.

**Migration:**
- `set-sentinel --spec X` → Start from web UI "Start Sentinel" button, or `set-orchestrate start --spec X`
- `set-sentinel --shutdown` → Use web UI "Stop Sentinel" button, or kill the orchestrator directly

### Requirement: CLI log rotation
The `set-sentinel-rotate` CLI helper SHALL be removed. Log rotation was only invoked by the bash supervisor script.

**Reason:** No other consumer calls this script. The web UI and Claude skill don't use it.

**Migration:** None needed — rotation was an internal detail of the bash supervisor.
