## 1. Skill

- [x] 1.1 Write `.claude/skills/set/blueprint/SKILL.md`: inputs, phase 1 research, phase 2 blueprint, phase 3 optional visual page, handoff, and the rules (sources, inference marking, ⚠ assumptions tied to test ids, price options never chosen, account ownership, offer comes after).
- [x] 1.2 Write `.claude/skills/set/blueprint/templates/research.md` with the summary table, the verdict scale and the per-item skeleton ending in the hands-on test.
- [x] 1.3 Write `.claude/skills/set/blueprint/templates/architecture-plan.md` with every required section as a placeholder.
- [x] 1.4 Write `.claude/commands/set/blueprint.md`.

## 2. Verification

- [x] 2.1 Add `tests/unit/test_blueprint_skill.py`: the sources exist, the frontmatter names the skill, the skill and templates carry every required section and the verdict scale.
- [x] 2.2 Run the test and `openspec validate --strict add-architecture-blueprint-skill`.
- [x] 2.3 Confirm no consumer name, partner name or client content appears in any new file.
