## 1. Heartbeat Helper

- [x] 1.1 Add `_signal_alive(state_file, event_bus)` helper function to `engine.py` that emits `WATCHDOG_HEARTBEAT` via event bus and touches state file mtime via `os.utime` [REQ: heartbeat-helper-function]
- [x] 1.2 Handle edge cases: event_bus=None (skip emit), OSError on utime (log warning, don't raise) [REQ: heartbeat-helper-function]

## 2. Bracket Long-Running Operations

- [x] 2.1 Add `_signal_alive()` call before and after `_poll_active_changes()` in monitor loop [REQ: pre-operation-heartbeat-emission]
- [x] 2.2 Add `_signal_alive()` call before and after `_drain_merge_then_dispatch()` in monitor loop [REQ: pre-operation-heartbeat-emission]
- [x] 2.3 Add `_signal_alive()` call before and after `_dispatch_ready_safe()` in monitor loop [REQ: pre-operation-heartbeat-emission]

## 3. Tests

- [x] 3.1 Unit test: `_signal_alive` emits heartbeat event when event_bus is provided [REQ: heartbeat-helper-function]
- [x] 3.2 Unit test: `_signal_alive` touches state file mtime [REQ: heartbeat-helper-function]
- [x] 3.3 Unit test: `_signal_alive` handles None event_bus without error [REQ: heartbeat-helper-function]
- [x] 3.4 Unit test: `_signal_alive` handles missing state file without raising [REQ: heartbeat-helper-function]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `_dispatch_ready_safe()` takes 120+ seconds THEN sentinel idle timer was reset before the call [REQ: pre-operation-heartbeat-emission, scenario: dispatch-takes-longer-than-poll-interval]
- [x] AC-2: WHEN `_drain_merge_then_dispatch()` takes 60+ seconds THEN heartbeat was emitted before the call [REQ: pre-operation-heartbeat-emission, scenario: merge-queue-drain-blocks-the-loop]
- [x] AC-3: WHEN dispatch completes after 90s and merge starts immediately THEN heartbeat was emitted between operations [REQ: post-operation-heartbeat-emission, scenario: back-to-back-long-operations]
- [x] AC-4: WHEN monitor runs without event bus THEN helper touches mtime without error [REQ: heartbeat-helper-function, scenario: event-bus-is-none]
- [x] AC-5: WHEN state file is missing THEN helper logs warning and continues [REQ: heartbeat-helper-function, scenario: state-file-does-not-exist]
