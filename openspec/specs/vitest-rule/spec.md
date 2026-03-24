# Vitest Planning Rule

## Requirements

- PLAN-TEST-001: `planning_rules.txt` MUST explicitly state that the infrastructure/foundation change creates package.json with a `test` script (vitest) and vitest in devDependencies.
- PLAN-TEST-002: The rule MUST say "Do NOT defer test runner setup to later changes" — the foundation change owns all tooling setup.
