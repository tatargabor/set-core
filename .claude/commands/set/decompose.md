Decompose a specification into an orchestration execution plan using agent-based analysis.

Usage: /set:decompose [spec-path]

This runs the decomposition skill which:
1. Reads the spec document
2. Explores the codebase for existing implementations
3. Checks project knowledge, requirements, and project type
4. Recalls relevant planning memories
5. Generates `orchestration-plan.json`

If no spec path is provided, it will look for the spec configured in orchestration config.

Arguments:
- spec-path: Path to the spec file (e.g., `set/orchestration/specs/v12.md`)

Example: `/set:decompose set/orchestration/specs/v12-minicrm.md`
