"""set-project-example: Example project type plugin for SET (ShipExactlyThis).

Demonstrates how to build a custom project type on top of set-core,
using a "Dungeon Builder" domain as a fun, self-contained example.

Domain: .dungeon YAML files describe rooms, corridors, monsters, and loot.
The build step generates ASCII maps and stat summaries.
Verification rules check graph integrity, loot balance, and reachability.
"""

from set_project_example.project_type import DungeonProjectType

__all__ = ["DungeonProjectType"]
