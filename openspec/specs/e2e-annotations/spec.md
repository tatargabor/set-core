# Spec: E2E Smoke/Functional Annotations

## REQ-ANNO-001: Smoke output always persisted
- WHEN a smoke phase completes (pass or fail)
- THEN `smoke_e2e_output` is saved to state
- AND `smoke_test_count`, `own_test_count`, `inherited_file_count` are saved

## REQ-ANNO-002: E2E panel shows two sections per change
- WHEN a change has both smoke and functional results
- THEN the E2E panel shows "SMOKE (inherited)" and "FUNCTIONAL (own)" sections separately
- AND each section has its own badge, test count, and timing

## REQ-ANNO-003: Summary includes smoke/functional breakdown
- WHEN viewing the E2E panel summary line
- THEN it shows total smoke and functional counts alongside pass/fail totals
