# Spec: verify-dead-agent-detection

## ADDED Requirements

## IN SCOPE
- Detecting dead Claude CLI processes inside alive terminal wrapper PIDs
- Recovering changes stuck in "verifying" status with dead inner processes
- Transitioning orphaned "verifying" changes to "stalled" for watchdog recovery

## OUT OF SCOPE
- Changing how `ralph_pid` is stored (terminal wrapper PID stays as-is)
- Modifying the wt-loop process management or PTY allocation
- Adding separate PID tracking for inner Claude processes

### Requirement: Poll detects dead verify agent

The monitor's `_poll_active_changes` SHALL detect when a change in "verifying" status has a dead agent process and transition it to "stalled" for watchdog recovery.

#### Scenario: Terminal wrapper alive but Claude CLI dead
- **WHEN** a change has orch status "verifying" and `ralph_pid` points to a terminal wrapper that is alive but has no child Claude CLI process
- **THEN** the monitor SHALL mark the change as "stalled" with reason "dead_verify_agent"

#### Scenario: Both terminal wrapper and Claude CLI dead
- **WHEN** a change has orch status "verifying" and `ralph_pid` is dead
- **THEN** the monitor SHALL mark the change as "stalled" with reason "dead_verify_agent"

### Requirement: Verifying status has timeout guard

Changes in "verifying" status SHALL have a maximum duration timeout, after which they are marked stalled regardless of PID status.

#### Scenario: Verify timeout exceeded
- **WHEN** a change has been in "verifying" status for longer than `verify_timeout` seconds (default 600s)
- **THEN** the monitor SHALL mark the change as "stalled" with reason "verify_timeout"

### Requirement: Stalled verify changes are recoverable

Changes marked stalled from a verify failure SHALL be eligible for watchdog resume, which re-dispatches the verify gate.

#### Scenario: Watchdog resumes stalled verify
- **WHEN** the watchdog detects a stalled change that was previously "verifying"
- **THEN** the change SHALL be set back to "running" and the agent re-dispatched to complete verify
