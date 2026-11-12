"""set:blueprint — the deployed sources exist and carry what the spec requires.

The skill ships through the provenance-guarded `.claude/skills/set/` and
`.claude/commands/set/` trees, so a missing or partial source would deploy
silently. These checks are on the SOURCE; the deploy copies it verbatim.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "set" / "blueprint"
SKILL = SKILL_DIR / "SKILL.md"
RESEARCH = SKILL_DIR / "templates" / "research.md"
PLAN = SKILL_DIR / "templates" / "architecture-plan.md"
COMMAND = REPO_ROOT / ".claude" / "commands" / "set" / "blueprint.md"

VERDICTS = ["works", "works with caveat", "doesn't", "unknown"]


def test_sources_exist_so_the_deploy_cannot_silently_deploy_nothing():
    for path in (SKILL, RESEARCH, PLAN, COMMAND):
        assert path.is_file(), path


def test_frontmatter_names_the_skill():
    lines = SKILL.read_text().splitlines()
    assert lines[0] == "---"
    assert "name: set:blueprint" in lines[1:4]
    assert any(line.startswith("description: ") for line in lines[1:5])


def test_the_verdict_scale_is_in_the_skill_and_the_research_template():
    for path in (SKILL, RESEARCH):
        text = path.read_text()
        for verdict in VERDICTS:
            assert verdict in text, f"{path.name} lacks verdict {verdict!r}"


def test_the_plan_template_carries_every_required_section():
    text = PLAN.read_text()
    for heading in (
        "The design in five lines",
        "Where things run",
        "How the parts talk",
        "Account ownership",
        "stores and ownership",
        "Requirement → component mapping",
        "Failure modes and monitoring",
        "Security and data protection",
        "Effort estimate",
        "Monthly running costs",
        "Tests that gate the price",
    ):
        assert heading in text, f"plan template lacks {heading!r}"
    assert "```mermaid" in text, "the deployment diagram placeholder is Mermaid"
    assert "Revocable by" in text, "every key row names who can revoke it"


def test_the_skill_never_lets_the_agent_choose_the_price_option():
    text = SKILL.read_text()
    assert "Never choose one" in text
    assert "⚠" in text and "test id" in text
