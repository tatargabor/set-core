"""Dungeon Builder — generates maps and stats from .dungeon YAML files.

Usage:
    python -m set_project_example.build [dungeon_dir] [output_dir]

This is the "build step" for the dungeon project type. It reads .dungeon
YAML files and produces:
  - .map files: UTF-8 dungeon maps with box-drawing characters
  - .stats files: monster counts, loot values, difficulty scores
  - index.md: summary of all dungeons
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


def parse_dungeon(path: Path) -> Dict[str, Any]:
    """Parse a .dungeon YAML file into a dict.

    Accepts both YAML and JSON format (YAML is a superset of JSON).
    """
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text)


def build_map(dungeon: Dict[str, Any]) -> str:
    """Generate a UTF-8 map from a parsed dungeon.

    Produces a box-drawing layout showing rooms, monsters, loot, and exits.
    """
    rooms = dungeon.get("rooms", [])
    if not rooms:
        return "(empty dungeon)\n"

    lines: List[str] = []

    # Title
    name = dungeon.get("name", "Unknown Dungeon")
    difficulty = dungeon.get("difficulty", "?")
    lines.append(f"{'=' * 40}")
    lines.append(f"  {name}")
    lines.append(f"  Difficulty: {difficulty}")
    lines.append(f"{'=' * 40}")
    lines.append("")

    # Draw each room as a box
    for room in rooms:
        rid = room["id"]
        monsters = room.get("monsters", [])
        loot = room.get("loot", [])
        exits = room.get("exits", [])
        requires = room.get("requires", "")

        # Room box
        width = max(len(rid) + 4, 20)
        lines.append(f"+{'-' * width}+")
        lines.append(f"| {rid.upper():<{width - 2}} |")

        if requires:
            lines.append(f"| {'[LOCKED] ' + requires:<{width - 2}} |")
        if monsters:
            m_str = ", ".join(monsters)
            lines.append(f"| {'[M] ' + m_str:<{width - 2}} |")
        if loot:
            l_str = ", ".join(loot)
            lines.append(f"| {'[*] ' + l_str:<{width - 2}} |")

        lines.append(f"+{'-' * width}+")
        exits_str = " -> ".join(exits) if exits else "(dead end)"
        lines.append(f"  exits: {exits_str}")
        lines.append("")

    return "\n".join(lines)


def build_stats(dungeon: Dict[str, Any]) -> str:
    """Generate stats summary from a parsed dungeon."""
    rooms = dungeon.get("rooms", [])
    total_monsters = sum(len(r.get("monsters", [])) for r in rooms)
    total_loot = sum(len(r.get("loot", [])) for r in rooms)
    locked_rooms = sum(1 for r in rooms if r.get("requires"))
    dead_ends = sum(1 for r in rooms if not r.get("exits"))

    # Simple difficulty score
    difficulty_multiplier = {
        "easy": 1.0, "medium": 1.5, "hard": 2.0, "nightmare": 3.0,
    }
    base_diff = dungeon.get("difficulty", "medium")
    multiplier = difficulty_multiplier.get(base_diff, 1.5)
    score = (total_monsters * 10 + locked_rooms * 15 - total_loot * 3) * multiplier

    lines = [
        f"Dungeon: {dungeon.get('name', 'Unknown')}",
        f"Rooms: {len(rooms)}",
        f"Monsters: {total_monsters}",
        f"Loot items: {total_loot}",
        f"Locked rooms: {locked_rooms}",
        f"Dead ends: {dead_ends}",
        f"Difficulty: {base_diff} (x{multiplier})",
        f"Challenge score: {score:.0f}",
    ]
    return "\n".join(lines)


def build_index(dungeons: List[Dict[str, Any]], paths: List[Path]) -> str:
    """Generate an index.md listing all dungeons."""
    lines = ["# Dungeon Index", ""]

    for dungeon, path in zip(dungeons, paths):
        name = dungeon.get("name", path.stem)
        rooms = dungeon.get("rooms", [])
        difficulty = dungeon.get("difficulty", "?")
        monsters = sum(len(r.get("monsters", [])) for r in rooms)
        lines.append(f"- **{name}** (`{path.name}`) — {len(rooms)} rooms, "
                      f"{monsters} monsters, difficulty: {difficulty}")

    return "\n".join(lines)


def main(dungeon_dir: str = "dungeons", output_dir: str = "output") -> int:
    """Build all .dungeon files and write output."""
    src = Path(dungeon_dir)
    dst = Path(output_dir)

    if not src.is_dir():
        print(f"No dungeon directory found at {src}")
        return 1

    dungeon_files = sorted(src.glob("*.dungeon"))
    if not dungeon_files:
        print(f"No .dungeon files found in {src}")
        return 1

    dst.mkdir(parents=True, exist_ok=True)

    dungeons = []
    paths = []

    for dfile in dungeon_files:
        print(f"Building {dfile.name}...")
        dungeon = parse_dungeon(dfile)
        dungeons.append(dungeon)
        paths.append(dfile)

        # Write .map
        map_content = build_map(dungeon)
        (dst / f"{dfile.stem}.map").write_text(map_content, encoding="utf-8")

        # Write .stats
        stats_content = build_stats(dungeon)
        (dst / f"{dfile.stem}.stats").write_text(stats_content, encoding="utf-8")

    # Write index
    index_content = build_index(dungeons, paths)
    (dst / "index.md").write_text(index_content, encoding="utf-8")

    print(f"\nBuilt {len(dungeons)} dungeon(s) -> {dst}/")
    return 0


if __name__ == "__main__":
    dungeon_dir = sys.argv[1] if len(sys.argv) > 1 else "dungeons"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
    sys.exit(main(dungeon_dir, output_dir))
