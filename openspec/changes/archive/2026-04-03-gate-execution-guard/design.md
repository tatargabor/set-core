# Design: Gate Execution Guard

## Approach

Add a `gates_executed` counter in `_run_integration_gates()`. Increment for each gate that actually runs a subprocess command. At the end, if counter is 0 and the change type is not "infrastructure", log a WARNING and emit a `GATE_SKIP_WARNING` event.

## Decision: Warn vs Block

**Warn, don't block.** Blocking would break runs where no profile is configured intentionally. The warning makes the problem visible in logs and events so the sentinel or operator can investigate.

## Implementation

```python
# At start of _run_integration_gates:
gates_executed = 0

# After each gate subprocess runs:
gates_executed += 1

# At end, before return True:
if gates_executed == 0:
    change_type = getattr(change, 'change_type', '') or 'feature'
    if change_type not in ('infrastructure', 'config', 'docs'):
        logger.warning(
            "Integration gate: NO gates executed for %s (type=%s) — "
            "check project-type.yaml and profile detection",
            change_name, change_type,
        )
        if event_bus:
            event_bus.emit("GATE_SKIP_WARNING", change=change_name, data={
                "reason": "no_gates_executed", "change_type": change_type})
```
