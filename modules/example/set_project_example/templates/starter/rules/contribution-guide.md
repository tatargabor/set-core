# Contribution Guide

## Adding a New Dungeon

1. Create `dungeons/<name>.dungeon` with valid YAML
2. Include at least one room with `id: entrance`
3. Run `python -m set_project_example.build` to generate the map
4. Verify the generated `output/<name>.map` looks correct
5. Run `pytest` to validate integrity rules

## Adding a New Monster

1. Add the monster entry to `bestiary.yaml`
2. Include: id, name, health, attack, description
3. Reference it in a dungeon room's `monsters` list
4. Rebuild to see updated stats

## Modifying Shared Files

The following files are cross-cutting — changes affect all dungeons:
- `bestiary.yaml` — monster definitions
- `loot-table.yaml` — loot item values and rarities

Changes to these files are automatically flagged for review by the orchestrator.
