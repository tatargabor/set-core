# Proposal: Web Dashboard E2E Tests

## Problem

The web dashboard has recurring UI bugs that go undetected until manual inspection:
- Gate icons missing on Phases tab (PhaseView didn't pass `spec_coverage_result`)
- Token values showing near-zero (input_tokens didn't include cache_read)
- Session data not displaying
- Status colors wrong after refactors

Every refactor or feature addition risks breaking existing functionality with no automated way to verify.

## Solution

Add Playwright E2E tests that run against the **live server** with a **real project** (no mocks). Tests compare API data against rendered UI — if any field mapping breaks, the test fails.

## Scope

- Playwright setup in `web/` (config, helpers, scripts)
- 10 spec files covering all dashboard tabs and interactions
- Test approach: fetch API data, then assert UI renders it correctly
- HTML test report for readable bug diagnosis
- CLAUDE.md documentation so agents know how to run these tests

## Out of scope

- WebSocket testing (REST fallback is sufficient)
- Visual/screenshot regression
- Manager page issues/mutes CRUD testing
- Voice input testing

## Configuration

- `E2E_PROJECT` env var: which registered project to test against
- `E2E_BASE_URL` env var: server URL (default `http://localhost:7400`)
- Requires: running `set-orch-core` server + at least one project with completed orchestration
