## Requirements

### Requirement: Metrics enabled during benchmark runs
Both init scripts (`init-baseline.sh` and `init-with-memory.sh`) must create the metrics enablement flag so that hook invocations during the benchmark are recorded to SQLite.

#### Scenario: Init script enables metrics
- **WHEN** `init-baseline.sh` or `init-with-memory.sh` runs
- **THEN** `~/.local/share/set-core/metrics/.enabled` exists after completion

#### Scenario: Metrics collected during benchmark
- **WHEN** a Claude session runs in either benchmark directory with hooks deployed
- **THEN** per-hook metrics (query, result_count, relevance_scores, duration_ms, dedup_hit) are appended to the session cache and flushed to `~/.local/share/set-core/metrics/metrics.db` on session Stop

---

### Requirement: Post-run metrics analysis documented
The run-guide must include instructions for analyzing metrics after both runs complete.

#### Scenario: User runs post-run analysis
- **WHEN** both benchmark runs complete
- **THEN** the run-guide provides commands to generate a metrics report comparing injection quality between Run A and Run B

---

### Requirement: Run-guide reflects v7 status
The run-guide "Current Status" section must reflect that test fixes are implemented and what v7 adds.

#### Scenario: User reads run-guide
- **WHEN** user opens run-guide.md
- **THEN** the Current Status section says v7, lists test fixes as done, and describes metrics integration as the v7 addition

---

### Requirement: Recall-verify emphasis in with-memory CLAUDE.md
The with-memory.md must include stronger guidance about verifying recalled information against current code state.

#### Scenario: Agent recalls implementation details
- **WHEN** Run B agent uses `set-memory recall` and receives results about file locations or implementations
- **THEN** the CLAUDE.md instructs it to verify the recalled information against current code before acting on it
