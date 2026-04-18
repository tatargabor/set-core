# Spec: Design Verify Gate (delta)

## REMOVED Requirements

### Requirement: Design compliance section in code review

**Reason:** The inline code review section never executed reliably (per `project_review_gate_not_running.md`: engine bypasses review pipeline via direct merge queue). Replaced by a standalone integration gate (`design-fidelity`) that performs visual regression and runs in the merge pipeline.

**Migration:** Consumers gain stronger drift detection automatically once `design-fidelity` is registered (see `design-fidelity-gate` capability). No consumer action required other than ensuring v0-export and content-fixtures.yaml are present.

### Requirement: Design compliance severity

**Reason:** Severity classification is no longer relevant — the new fidelity gate is binary pass/fail (with `warn_only` mode for emergency mitigation). Token-grep style WARNINGs in code review are removed.

**Migration:** Use the new gate's `warn_only: true` config flag if a project needs non-blocking drift detection during transition.

### Requirement: Design token extraction for review

**Reason:** Token extraction is no longer part of the code review path. Tokens are still extracted by the web module's `v0-design-source` provider (for the agent's dispatch context quick-reference), but not for review-time comparison.

**Migration:** No action — the new fidelity gate compares rendered output, not source tokens. If a project needs source-level token compliance, consider a custom lint rule outside this framework.
