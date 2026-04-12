# Proposal: E2E Smoke/Functional UI Annotations

## Problem

The E2E test tab in the digest view shows a flat list of tests per change with no distinction between smoke (inherited) and functional (own) tests. The two-phase gate pipeline already separates these in the backend (merger.py), but:

1. **Smoke output not always saved** — only saved on failure (`smoke_e2e_output`), not on success
2. **No smoke test count/stats in state** — `smoke_stats` field exists but is never populated
3. **Frontend shows one flat list** — `E2EPanel` parses `e2e_output` only, ignoring smoke data
4. **No timing breakdown** — `gate_e2e_smoke_ms` and `gate_e2e_own_ms` are saved but not displayed

## Changes

1. **Backend (merger.py)**: Always save `smoke_e2e_output` (not just on failure) and populate `smoke_test_count`, `own_test_count`, `inherited_file_count` fields in state
2. **Frontend (DigestView.tsx)**: Show smoke vs functional sections per change with badge annotations, timing, and test counts
