"""Dungeon Builder project type — example plugin for SET.

This file demonstrates every extension point available in the ProjectType
interface. Each method includes comments explaining what it does and why
you'd override it in a real project type.

Extension points demonstrated:
  - info              → metadata + parent declaration
  - get_templates()   → starter files for new projects
  - get_verification_rules()  → domain integrity checks
  - get_orchestration_directives() → parallel work coordination
  - planning_rules()  → injected into decompose prompt
  - security_checklist() → proposal.md checklist items
  - security_rules_paths() → rules for verify retry context
  - generated_file_patterns() → auto-resolve merge conflicts
  - detect_test_command() → auto-detect test runner
  - detect_build_command() → auto-detect build step
  - ignore_patterns() → exclude from analysis
  - gate_overrides()  → per-change-type verification gates
"""

from pathlib import Path
from typing import List, Optional

from set_orch.profile_loader import CoreProfile
from set_orch.profile_types import (
    OrchestrationDirective,
    ProjectTypeInfo,
    TemplateInfo,
    VerificationRule,
)


class DungeonProjectType(CoreProfile):
    """Dungeon Builder project type.

    Extends BaseProjectType with dungeon-specific verification rules
    and orchestration directives. Demonstrates how any domain can plug
    into the set-core framework.

    Domain concepts:
    - .dungeon files: YAML defining rooms, exits, monsters, loot
    - Build: generates ASCII maps + stat files from .dungeon sources
    - Verification: graph integrity, loot balance, reachability
    """

    # ── Metadata ──────────────────────────────────────────────

    @property
    def info(self) -> ProjectTypeInfo:
        return ProjectTypeInfo(
            name="dungeon",
            version="0.1.0",
            description="Dungeon Builder — example project type for learning set-core",
            parent="base",  # inherits base rules (file-size, no-secrets, todo-tracking)
        )

    # ── Templates ─────────────────────────────────────────────

    def get_templates(self) -> List[TemplateInfo]:
        return [
            TemplateInfo(
                id="starter",
                description="Starter dungeon project with example .dungeon files and rules",
                template_dir="templates/starter",
            ),
        ]

    # ── Verification Rules ────────────────────────────────────
    #
    # These rules run during opsx:verify to catch problems.
    # Each rule has an id, description, check type, severity, and config.

    def get_verification_rules(self) -> List[VerificationRule]:
        base_rules = super().get_verification_rules()

        dungeon_rules = [
            # 1. Every room exit must point to an existing room
            VerificationRule(
                id="exit-target-exists",
                description="Room exits must reference existing room IDs",
                check="cross-file-key-parity",
                severity="error",
                config={
                    "source": {"pattern": "dungeons/*.dungeon", "field": "rooms[].exits[]"},
                    "target": {"pattern": "dungeons/*.dungeon", "field": "rooms[].id"},
                },
            ),
            # 2. No orphan rooms (rooms with no incoming exits)
            VerificationRule(
                id="no-orphan-rooms",
                description="Every room (except entrance) must be reachable from at least one other room",
                check="graph-reachability",
                severity="warning",
                config={
                    "pattern": "dungeons/*.dungeon",
                    "nodes": "rooms[].id",
                    "edges": "rooms[].exits[]",
                    "root": "entrance",
                },
            ),
            # 3. Locked rooms must have their key available somewhere
            VerificationRule(
                id="key-available-for-locks",
                description="If a room has 'requires: key_name', that key must exist as loot in a reachable room",
                check="cross-reference",
                severity="error",
                config={
                    "groups": [{
                        "name": "lock-key-consistency",
                        "files": [
                            {"role": "locks", "pattern": "dungeons/*.dungeon", "field": "rooms[].requires"},
                            {"role": "keys", "pattern": "dungeons/*.dungeon", "field": "rooms[].loot[]"},
                        ],
                    }],
                },
            ),
            # 4. Dungeon difficulty must be a valid value
            VerificationRule(
                id="valid-difficulty",
                description="Dungeon difficulty must be one of: easy, medium, hard, nightmare",
                check="pattern-audit",
                severity="warning",
                config={
                    "pattern": "dungeons/*.dungeon",
                    "match": r"^difficulty:\s*(?!easy|medium|hard|nightmare)",
                },
            ),
            # 5. No duplicate room IDs within a dungeon
            VerificationRule(
                id="unique-room-ids",
                description="Room IDs must be unique within each .dungeon file",
                check="unique-keys",
                severity="error",
                config={
                    "pattern": "dungeons/*.dungeon",
                    "field": "rooms[].id",
                    "scope": "per-file",
                },
            ),
            # 6. Monster names should be from a known bestiary
            VerificationRule(
                id="known-monsters",
                description="Monsters should be defined in bestiary.yaml",
                check="cross-file-key-parity",
                severity="warning",
                config={
                    "source": {"pattern": "dungeons/*.dungeon", "field": "rooms[].monsters[]"},
                    "target": {"file": "bestiary.yaml", "field": "monsters[].id"},
                },
            ),
        ]

        return base_rules + dungeon_rules

    # ── Orchestration Directives ──────────────────────────────
    #
    # These directives tell the orchestrator how to coordinate
    # parallel changes safely.

    def get_orchestration_directives(self) -> List[OrchestrationDirective]:
        base_directives = super().get_orchestration_directives()

        dungeon_directives = [
            # Serialize changes to the same dungeon file
            OrchestrationDirective(
                id="no-parallel-dungeon-edit",
                description="Serialize changes that modify the same .dungeon file to prevent merge conflicts",
                trigger='change-modifies("dungeons/*.dungeon")',
                action="serialize",
                config={"with": 'changes-modifying("dungeons/*.dungeon")'},
            ),
            # Regenerate maps after dungeon changes
            OrchestrationDirective(
                id="rebuild-maps",
                description="Regenerate ASCII maps after .dungeon file changes",
                trigger='change-modifies("dungeons/*.dungeon")',
                action="post-merge",
                config={"command": "python -m set_project_example.build"},
            ),
            # Warn if bestiary changes while dungeons reference old monsters
            OrchestrationDirective(
                id="bestiary-change-review",
                description="Flag bestiary changes for review — dungeons may reference removed monsters",
                trigger='change-modifies("bestiary.yaml")',
                action="flag-for-review",
            ),
            # Cross-cutting: shared loot table
            OrchestrationDirective(
                id="loot-table-review",
                description="Flag changes to shared loot table for cross-cutting review",
                trigger='change-modifies("loot-table.yaml")',
                action="flag-for-review",
            ),
        ]

        return base_directives + dungeon_directives

    # ── Profile Methods (Engine Integration) ──────────────────
    #
    # These methods let the engine auto-detect how to work with
    # your project. Override what makes sense for your domain.

    def planning_rules(self) -> str:
        """Quality patterns injected into the decompose/planning prompt.

        For short rules, inline strings work fine (as shown here).
        For longer rules, load from a file — see set-project-web's approach:
            rules_file = Path(__file__).parent / "planning_rules.txt"
            return rules_file.read_text() if rules_file.is_file() else ""
        """
        return (
            "## Dungeon Builder Planning Rules\n"
            "- Each .dungeon file should be self-contained (one dungeon per file)\n"
            "- The entrance room is always the root of the room graph\n"
            "- Locked rooms create dependencies — plan key-placement changes before lock changes\n"
            "- Bestiary changes are cross-cutting — flag them for review\n"
        )

    def security_rules_paths(self, project_path: str) -> List[Path]:
        """Return dungeon integrity rules for injection into verify retry context.

        When code review finds CRITICAL issues, these rule files are loaded
        and injected into the retry prompt so the agent knows the constraints.
        """
        rules_dir = Path(project_path) / ".claude" / "rules"
        paths = list(rules_dir.glob("dungeon-*.md"))
        if not paths:
            # Fall back to bundled template rules
            template_rules = Path(__file__).parent / "templates" / "starter" / "rules"
            p = template_rules / "dungeon-integrity.md"
            if p.is_file():
                paths.append(p)
        return paths

    def security_checklist(self) -> str:
        """Security checklist items for proposal.md (domain-appropriate)."""
        return (
            "- [ ] Dungeon graphs have no infinite loops (room A→B→A with no escape)\n"
            "- [ ] Loot values don't overflow difficulty scaling calculations\n"
            "- [ ] User-supplied dungeon names are sanitized in output filenames"
        )

    def generated_file_patterns(self) -> List[str]:
        """Files that are generated and can be auto-resolved during merge."""
        return [
            "output/*.map",      # Generated ASCII maps
            "output/*.stats",    # Generated stat summaries
            "output/index.md",   # Generated dungeon index
        ]

    def detect_test_command(self, project_path: str) -> Optional[str]:
        """Detect test runner — checks for pytest config files and test directories."""
        p = Path(project_path)
        # Check pyproject.toml for [tool.pytest] section
        if (p / "pyproject.toml").is_file():
            try:
                import tomllib
                data = tomllib.loads((p / "pyproject.toml").read_text())
                if "pytest" in data.get("tool", {}):
                    return "pytest"
            except Exception:
                pass
        # Check for standalone pytest/unittest config files
        if (p / "pytest.ini").is_file() or (p / "setup.cfg").is_file():
            return "pytest"
        # Check for test files in tests/ directory
        tests_dir = p / "tests"
        if tests_dir.is_dir() and list(tests_dir.glob("test_*.py")):
            return "pytest"
        return None

    def detect_build_command(self, project_path: str) -> Optional[str]:
        """The build command generates maps from .dungeon files."""
        if list(Path(project_path).glob("dungeons/*.dungeon")):
            return "python -m set_project_example.build"
        return None

    def ignore_patterns(self) -> List[str]:
        """Patterns to ignore during digest/codemap generation."""
        return ["output/", "__pycache__", "*.pyc", ".venv"]

    def gate_overrides(self, change_type: str) -> dict:
        """Gate overrides per change type.

        - 'lore' changes (descriptions, flavor text): skip test requirement
        - 'bestiary' changes: need cross-cutting review
        """
        overrides = {
            "lore": {
                "test_files_required": False,
            },
            "bestiary": {
                "smoke": "warn",
            },
        }
        return overrides.get(change_type, {})
