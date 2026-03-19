"""Build dynamic system prompt for the orchestration chat agent.

Called on every claude invocation to provide fresh orchestration context.
The result is passed via --append-system-prompt so the agent always sees
the latest state alongside the project's CLAUDE.md.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("wt-web.chat-context")


def build_chat_context(project_path: Path) -> str:
    """Build the full system prompt appendix for the orchestration chat agent.

    Returns a string ready to pass to --append-system-prompt.
    """
    sections = [
        _role_section(),
        _state_section(project_path),
        _config_section(project_path),
        _commands_section(),
    ]
    return "\n\n".join(s for s in sections if s)


# ─── Sections ─────────────────────────────────────────────────────────


def _role_section() -> str:
    return """## Szereped

Te az orchestration supervisor vagy (Level 2 — reaktív).

Feladataid:
- Válaszolj a felhasználó kérdéseire az orchestration állapotáról
- A felhasználó kérésére avatkozz be: skip, pause, resume, restart loop
- NE avatkozz be magadtól — csak ha kérnek

FONTOS szabályok:
- Az aktuális orchestration státusz LENTEBB LÁTHATÓ ebben a promptban — NE olvasd újra a state fájlt, hacsak nem kérnek frissítést
- Státusz kérdésre válaszolj a promptban lévő adatokból, NE futtass parancsokat
- Csak akkor futtass parancsot ha: (1) a promptban nincs meg az info, VAGY (2) a user kifejezetten kéri
- SOHA ne futtasd ugyanazt a parancsot kétszer
- Egy kérdésre max 1-2 parancs, ne több
- Az ELSŐ üzenetre mindig köszönj és add meg a rövid státusz összefoglalót a promptban lévő adatokból (hány change, mi a státusz, hány kész/futó/pending). NE futtass parancsot ehhez.

Válaszolj magyarul. Legyél tömör."""


def _state_section(project_path: Path) -> str:
    state = _read_state(project_path)
    if state is None:
        return "## Orchestration státusz\n\nNincs aktív orchestration (state fájl nem található)."

    if isinstance(state, str):
        # Error message
        return f"## Orchestration státusz\n\n{state}"

    # Format summary
    lines = ["## Orchestration státusz\n"]

    status = state.get("status", "unknown")
    lines.append(f"**Állapot:** {status}")

    changes = state.get("changes", [])
    if not changes:
        lines.append("Nincsenek change-ek.")
        return "\n".join(lines)

    # Summary counts
    by_status: dict[str, int] = {}
    for c in changes:
        s = c.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    summary_parts = [f"{v} {k}" for k, v in sorted(by_status.items())]
    lines.append(f"**Összesen:** {len(changes)} change ({', '.join(summary_parts)})")

    total_tokens = sum(c.get("tokens_used", 0) for c in changes)
    if total_tokens:
        lines.append(f"**Token összesen:** {total_tokens:,}")

    # Change table
    lines.append("")
    lines.append("| Change | Status | Tokens | Model |")
    lines.append("|--------|--------|--------|-------|")
    for c in changes:
        name = c.get("name", "?")
        s = c.get("status", "?")
        tok = c.get("tokens_used", 0)
        model = c.get("model", "-")
        tok_str = f"{tok:,}" if tok else "-"
        lines.append(f"| {name} | {s} | {tok_str} | {model or '-'} |")

    return "\n".join(lines)


def _config_section(project_path: Path) -> str:
    config = _read_config(project_path)
    if config is None:
        return ""  # No config → omit section entirely

    directives = config.get("directives", config)

    lines = ["## Orchestration config\n"]
    keys = [
        ("max_parallel", "Max parallel"),
        ("token_budget", "Token budget"),
        ("token_hard_limit", "Token hard limit"),
        ("time_limit", "Time limit"),
        ("test_command", "Test command"),
        ("smoke_command", "Smoke command"),
        ("default_model", "Default model"),
        ("review_model", "Review model"),
        ("merge_policy", "Merge policy"),
        ("checkpoint_every", "Checkpoint every"),
    ]
    for key, label in keys:
        val = directives.get(key)
        if val is not None and val != "" and val != 0:
            lines.append(f"- **{label}:** {val}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _commands_section() -> str:
    return """## Elérhető parancsok

### Lekérdezés
- `cat wt/orchestration/orchestration-state.json | python3 -m json.tool` — teljes state
- `wt-orch-core state query --file wt/orchestration/orchestration-state.json --status running` — futó change-ek
- `wt-orch-core state get --file wt/orchestration/orchestration-state.json --change <name> --field status` — egy mező
- `tail -50 .claude/orchestration.log` — utolsó log sorok
- `tail -20 wt/orchestration/orchestration-events.jsonl` — utolsó események
- `git worktree list` — aktív worktree-k
- `wt-loop monitor <change-id>` — Ralph loop státusz

### Vezérlés
- `wt-orchestrate skip <change-name> --reason "text"` — change kihagyása
- `wt-orchestrate pause <change-name>` — change szüneteltetése
- `wt-orchestrate resume <change-name>` — change folytatása
- `wt-loop start <change-id> "<task>"` — Ralph loop indítása
- `wt-loop stop <change-id>` — Ralph loop leállítása

### Worktree
- `wt-new <change-id>` — worktree létrehozása
- `wt-close <change-id>` — worktree törlése
- `wt-merge <change-id>` — worktree merge

### Kommunikáció
- `wt-msg <recipient> "<message>"` — üzenet küldése agentnek"""


# ─── File readers ─────────────────────────────────────────────────────


def _read_state(project_path: Path) -> dict[str, Any] | str | None:
    """Read orchestration state. Returns dict, error string, or None."""
    # Try new location first, then legacy
    for rel in ["wt/orchestration/orchestration-state.json", "orchestration-state.json"]:
        path = project_path / rel
        if path.is_file():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read state: {e}")
                return "State fájl olvashatatlan."
    return None


def _read_config(project_path: Path) -> dict[str, Any] | None:
    """Read orchestration.yaml config. Returns dict or None."""
    path = project_path / ".claude" / "orchestration.yaml"
    if not path.is_file():
        return None

    try:
        # Use basic YAML parsing — avoid external dependency
        # orchestration.yaml is simple key: value format
        import yaml
        return yaml.safe_load(path.read_text())
    except ImportError:
        # Fallback: parse simple key: value YAML manually
        return _parse_simple_yaml(path)
    except Exception as e:
        logger.warning(f"Failed to read config: {e}")
        return None


def _parse_simple_yaml(path: Path) -> dict[str, Any] | None:
    """Minimal YAML parser for orchestration.yaml (flat key: value pairs)."""
    try:
        text = path.read_text()
        result: dict[str, Any] = {}
        current_section: dict[str, Any] | None = None
        current_key: str | None = None

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Top-level key (no indent)
            if not line.startswith(" ") and not line.startswith("\t") and ":" in stripped:
                key, _, val = stripped.partition(":")
                val = val.strip()
                if val:
                    result[key.strip()] = _yaml_value(val)
                else:
                    current_key = key.strip()
                    current_section = {}
                    result[current_key] = current_section
            # Indented key (under a section)
            elif current_section is not None and ":" in stripped:
                key, _, val = stripped.partition(":")
                val = val.strip()
                current_section[key.strip()] = _yaml_value(val)

        return result
    except Exception:
        return None


def _yaml_value(val: str) -> Any:
    """Convert a YAML string value to Python type."""
    if val in ("true", "True", "yes"):
        return True
    if val in ("false", "False", "no"):
        return False
    if val in ("null", "~", ""):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    # Strip quotes
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val
