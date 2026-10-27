## Why

Before a client offer is priced, the team has to know what the solution will run on, how
the parts talk to each other, which requirement each part serves, what can fail, and how
many hours it costs. Today that knowledge is assembled by hand in each consumer project,
in a different shape every time, and the price is often fixed before the building blocks
were checked. The first time it was done deliberately — a research pass over an internal
test list, then a full blueprint with diagrams, a requirement map, a sub-processor table,
an hours estimate against the price band and the tests that gate the price — it changed
the price and the architecture before the offer went out. The method is reusable; the
user asked for it to become part of the framework so that every future project produces
the same blueprint before its offer.

## What Changes

- A new skill, `set:blueprint`, deployed with the other `set/*` skills by `set-project init`.
  It guides an agent through three phases: research (verdict per open question, with
  sources and the hands-on test still to run), the architecture blueprint document, and
  an optional internal visual page built from the blueprint.
- Two output skeletons shipped inside the skill directory: `templates/research.md` and
  `templates/architecture-plan.md`, so every project's blueprint has the same sections.
- A matching `/set:blueprint` command file.
- A unit test asserting the sources exist and carry the sections the spec requires, so a
  deploy can never silently ship an empty or partial skill.

No code path, deploy mechanism or contract changes: the skill rides the existing
provenance-guarded `.claude/skills/set/` and `.claude/commands/set/` trees.

## Capabilities

### New Capabilities
- `architecture-blueprint`: The pre-offer architecture blueprint method — inputs, research
  verdicts, the required sections of the blueprint document, the marking of untested
  assumptions, the price-band check that presents options without choosing one, and the
  handoff.

### Modified Capabilities

(none)

## Impact

- `.claude/skills/set/blueprint/SKILL.md` — new
- `.claude/skills/set/blueprint/templates/research.md` — new
- `.claude/skills/set/blueprint/templates/architecture-plan.md` — new
- `.claude/commands/set/blueprint.md` — new
- `tests/unit/test_blueprint_skill.py` — new
- Consumers receive the skill on their next `set-project init` (new files are deployed;
  nothing existing is overwritten).
