"""Tests for the dungeon build step — map and stats generation.

These tests validate that the build step produces correct output
from .dungeon input files.
"""

import json

import pytest
from pathlib import Path

from set_project_example.build import (
    build_map,
    build_stats,
    build_index,
    parse_dungeon,
    main,
)


# ── Fixtures ──────────────────────────────────────────────

SIMPLE_DUNGEON = {
    "name": "Test Dungeon",
    "difficulty": "easy",
    "rooms": [
        {
            "id": "entrance",
            "description": "The way in",
            "exits": ["hallway"],
            "monsters": [],
            "loot": ["key"],
        },
        {
            "id": "hallway",
            "description": "A corridor",
            "exits": ["entrance", "boss_room"],
            "monsters": ["goblin"],
            "loot": [],
        },
        {
            "id": "boss_room",
            "description": "The final room",
            "exits": ["hallway"],
            "monsters": ["dragon"],
            "loot": ["golden_crown"],
            "requires": "key",
        },
    ],
}

EMPTY_DUNGEON = {
    "name": "Empty",
    "difficulty": "easy",
    "rooms": [],
}


# ── Map Generation ────────────────────────────────────────

class TestBuildMap:
    def test_includes_dungeon_name(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "Test Dungeon" in result

    def test_includes_difficulty(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "easy" in result

    def test_includes_room_ids(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "ENTRANCE" in result
        assert "HALLWAY" in result
        assert "BOSS_ROOM" in result

    def test_shows_monsters(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "goblin" in result
        assert "dragon" in result

    def test_shows_loot(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "key" in result
        assert "golden_crown" in result

    def test_shows_lock(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "[LOCKED]" in result

    def test_empty_dungeon(self):
        result = build_map(EMPTY_DUNGEON)
        assert "empty" in result.lower()

    def test_shows_exits(self):
        result = build_map(SIMPLE_DUNGEON)
        assert "exits:" in result

    def test_output_is_ascii_safe(self):
        """Map output uses only ASCII-safe characters (no emoji)."""
        result = build_map(SIMPLE_DUNGEON)
        result.encode("ascii")  # raises UnicodeEncodeError if non-ASCII


# ── Stats Generation ──────────────────────────────────────

class TestBuildStats:
    def test_counts_rooms(self):
        result = build_stats(SIMPLE_DUNGEON)
        assert "Rooms: 3" in result

    def test_counts_monsters(self):
        result = build_stats(SIMPLE_DUNGEON)
        assert "Monsters: 2" in result  # goblin + dragon

    def test_counts_loot(self):
        result = build_stats(SIMPLE_DUNGEON)
        assert "Loot items: 2" in result  # key + golden_crown

    def test_counts_locked_rooms(self):
        result = build_stats(SIMPLE_DUNGEON)
        assert "Locked rooms: 1" in result

    def test_shows_difficulty(self):
        result = build_stats(SIMPLE_DUNGEON)
        assert "easy" in result

    def test_calculates_challenge_score(self):
        result = build_stats(SIMPLE_DUNGEON)
        assert "Challenge score:" in result

    def test_difficulty_multiplier_affects_score(self):
        """Higher difficulty = higher challenge score."""
        easy = dict(SIMPLE_DUNGEON, difficulty="easy")
        hard = dict(SIMPLE_DUNGEON, difficulty="hard")

        easy_stats = build_stats(easy)
        hard_stats = build_stats(hard)

        easy_score = float(easy_stats.split("Challenge score: ")[1])
        hard_score = float(hard_stats.split("Challenge score: ")[1])
        assert hard_score > easy_score


# ── Index Generation ──────────────────────────────────────

class TestBuildIndex:
    def test_is_markdown(self):
        result = build_index([SIMPLE_DUNGEON], [Path("test.dungeon")])
        assert result.startswith("# Dungeon Index")

    def test_lists_dungeon(self):
        result = build_index([SIMPLE_DUNGEON], [Path("test.dungeon")])
        assert "Test Dungeon" in result
        assert "test.dungeon" in result

    def test_shows_room_count(self):
        result = build_index([SIMPLE_DUNGEON], [Path("test.dungeon")])
        assert "3 rooms" in result

    def test_multiple_dungeons(self):
        result = build_index(
            [SIMPLE_DUNGEON, EMPTY_DUNGEON],
            [Path("a.dungeon"), Path("b.dungeon")],
        )
        assert "Test Dungeon" in result
        assert "Empty" in result


# ── Parse ─────────────────────────────────────────────────

class TestParseDungeon:
    def test_parses_yaml(self, tmp_path):
        """Parses a .dungeon file (YAML format)."""
        dfile = tmp_path / "test.dungeon"
        dfile.write_text(
            'name: "My Dungeon"\n'
            "difficulty: easy\n"
            "rooms:\n"
            "  - id: entrance\n"
            "    exits: [hallway]\n"
        )
        result = parse_dungeon(dfile)
        assert result["name"] == "My Dungeon"
        assert result["rooms"][0]["id"] == "entrance"

    def test_parses_json(self, tmp_path):
        """Also accepts JSON (YAML is a superset of JSON)."""
        dfile = tmp_path / "test.dungeon"
        dfile.write_text(json.dumps({
            "name": "JSON Dungeon",
            "difficulty": "medium",
            "rooms": [{"id": "entrance", "exits": []}],
        }))
        result = parse_dungeon(dfile)
        assert result["name"] == "JSON Dungeon"


# ── Full Build (end-to-end) ──────────────────────────────

class TestMainBuild:
    def test_builds_output_from_dungeon_files(self, tmp_path):
        """End-to-end: .dungeon files -> .map + .stats + index.md"""
        dungeons_dir = tmp_path / "dungeons"
        dungeons_dir.mkdir()
        output_dir = tmp_path / "output"

        # Write a dungeon file (JSON format works too)
        (dungeons_dir / "test.dungeon").write_text(json.dumps({
            "name": "E2E Test",
            "difficulty": "medium",
            "rooms": [
                {"id": "entrance", "exits": ["room2"], "monsters": [], "loot": []},
                {"id": "room2", "exits": ["entrance"], "monsters": ["goblin"], "loot": ["coin"]},
            ],
        }))

        result = main(str(dungeons_dir), str(output_dir))
        assert result == 0

        # Check outputs exist
        assert (output_dir / "test.map").is_file()
        assert (output_dir / "test.stats").is_file()
        assert (output_dir / "index.md").is_file()

        # Check content
        map_content = (output_dir / "test.map").read_text()
        assert "E2E Test" in map_content
        assert "ENTRANCE" in map_content

        stats_content = (output_dir / "test.stats").read_text()
        assert "Rooms: 2" in stats_content

    def test_returns_1_if_no_dungeon_dir(self, tmp_path):
        result = main(str(tmp_path / "nonexistent"), str(tmp_path / "output"))
        assert result == 1

    def test_returns_1_if_no_dungeon_files(self, tmp_path):
        (tmp_path / "empty_dungeons").mkdir()
        result = main(str(tmp_path / "empty_dungeons"), str(tmp_path / "output"))
        assert result == 1
