## REMOVED Requirements

### Requirement: Per-change token budget enforcement
**Reason**: Replaced by progress-based trend detection (watchdog-progress-detection capability). Fixed complexity-based limits (S/M/L/XL) produced false positives — killing completed work. Progress detection examines actual iteration patterns instead of token counts.
**Migration**: Per-change budget enforcement is removed entirely. Global orchestrator-level `token_hard_limit` serves as runaway protection. The `_watchdog_check_token_budget()` and `_watchdog_token_limit_for_change()` functions are deleted. The call site in `watchdog_check()` is replaced with `_watchdog_check_progress()`.
