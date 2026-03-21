# Dungeon Integrity Rules

## Room Graph Consistency

1. **Every exit must lead somewhere** — if a room lists `exits: [hallway]`, a room with `id: hallway` must exist in the same dungeon file.

2. **No orphan rooms** — every room (except `entrance`) must be reachable by following exits from the entrance. Orphan rooms are dead content.

3. **Lock-key consistency** — if a room has `requires: rusty_key`, that key must appear as loot in some reachable room. Unreachable locks are softlocks.

4. **No duplicate IDs** — room IDs must be unique within each `.dungeon` file. Duplicate IDs cause undefined behavior in map generation.

## Loot & Monster Balance

5. **Known monsters only** — monsters referenced in rooms should exist in `bestiary.yaml`. Unknown monsters can't be rendered or balanced.

6. **Difficulty coherence** — a dungeon marked `easy` should not have `nightmare`-tier monsters. The build step calculates a challenge score; large discrepancies from the declared difficulty are flagged.

## File Conventions

- Dungeon files use `.dungeon` extension (YAML format)
- One dungeon per file
- File name matches the dungeon's internal `name` field (kebab-case)
- Generated output goes to `output/` — never edit generated files directly
