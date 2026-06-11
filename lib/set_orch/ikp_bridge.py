"""IKP (Integration Knowledge Pack) bridge for set-core orchestration.

Thin wrapper over the `ikp` Python package that provides set-core-native
functions for config loading, pack discovery, phase-appropriate layer
loading, and rule file injection into agent worktrees.

The ikp package is an optional dependency — all functions gracefully
degrade when it is not installed.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ikp_import_checked = False
_ikp_is_available = False


def _ikp_available() -> bool:
    global _ikp_import_checked, _ikp_is_available
    if _ikp_import_checked:
        return _ikp_is_available
    _ikp_import_checked = True
    try:
        import ikp.loader  # noqa: F401
        _ikp_is_available = True
    except ImportError:
        _ikp_is_available = False
        logger.debug("ikp package not installed — IKP pipeline disabled")
    return _ikp_is_available


@dataclass
class IkpConfig:
    packs: list[str]
    packs_dir: Path
    language: str
    ikp_version: str = "0.2"


def load_ikp_config(project_path: Path) -> IkpConfig | None:
    """Load .ikp.yaml from project root. Returns None if absent."""
    config_file = Path(project_path) / ".ikp.yaml"
    if not config_file.is_file():
        return None
    try:
        data = yaml.safe_load(config_file.read_text())
        if not isinstance(data, dict):
            logger.warning(".ikp.yaml is not a valid YAML mapping: %s", config_file)
            return None
        packs = data.get("packs", [])
        packs_dir_raw = data.get("packs_dir", "")
        language = data.get("language", "typescript")
        ikp_version = str(data.get("ikp", "0.2"))
        packs_dir = Path(packs_dir_raw).expanduser()
        return IkpConfig(
            packs=packs if isinstance(packs, list) else [],
            packs_dir=packs_dir,
            language=language,
            ikp_version=ikp_version,
        )
    except Exception:
        logger.warning("failed to parse .ikp.yaml at %s", config_file, exc_info=True)
        return None


def has_ikp_pipeline(
    project_path: Path, directives: dict[str, Any] | None = None,
) -> bool:
    """Whether this project has an active IKP pipeline."""
    dp = (directives or {}).get("ikp_pipeline", "auto")
    if dp == "none":
        return False
    if not _ikp_available():
        return False
    config = load_ikp_config(project_path)
    return config is not None and len(config.packs) > 0


_PHASE_LAYERS: dict[str, list[str]] = {
    "decompose": ["knowledge", "planning"],
    "dispatch": ["knowledge", "implementation"],
    "implement": ["knowledge", "implementation"],
    "verify": ["testing", "knowledge"],
}


def get_context_for_phase(
    phase: str, pack_names: list[str], ikp_config: IkpConfig,
) -> str:
    """Load IKP layers appropriate for the orchestration phase.

    Returns a markdown string with per-pack sections, or empty string
    on any failure.
    """
    if not _ikp_available():
        return ""
    try:
        from ikp.loader import load_pack
        from ikp.schema import Layer
    except ImportError:
        logger.warning("ikp package became unavailable during operation")
        return ""

    layer_names = _PHASE_LAYERS.get(phase, ["knowledge"])
    layers = []
    for name in layer_names:
        try:
            layers.append(Layer(name))
        except ValueError:
            logger.warning("unknown IKP layer name: %s", name)

    parts: list[str] = []
    for pack_name in pack_names:
        try:
            lang = ikp_config.language if Layer.IMPLEMENTATION in layers else None
            pack = load_pack(
                pack_name,
                layers=layers,
                language=lang,
                packs_dir=ikp_config.packs_dir,
            )
            ctx = pack.to_context()
            if ctx:
                parts.append(ctx)
        except Exception:
            logger.warning(
                "failed to load IKP pack %r for phase %r", pack_name, phase,
                exc_info=True,
            )
    return "\n\n---\n\n".join(parts)


def inject_rules_for_change(
    wt_path: Path,
    pack_names: list[str],
    phase: str,
    language: str,
    packs_dir: Path,
) -> list[Path]:
    """Write IKP implementation layers as rule files into worktree.

    Returns list of created file paths.
    """
    if not _ikp_available():
        return []
    try:
        from ikp.injector import inject_to_rules
        from ikp.schema import Layer
    except ImportError:
        logger.warning("ikp package became unavailable during rule injection")
        return []

    rules_dir = wt_path / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    layer_names = _PHASE_LAYERS.get(phase, ["knowledge", "implementation"])
    layers = []
    for name in layer_names:
        try:
            layers.append(Layer(name))
        except ValueError:
            pass

    created: list[Path] = []
    for pack_name in pack_names:
        try:
            result = inject_to_rules(
                pack_name,
                target_dir=rules_dir,
                layers=layers,
                language=language,
                packs_dir=packs_dir,
            )
            if result and result.exists():
                created.append(result)
                logger.info("injected IKP rules: %s", result)
        except Exception:
            logger.warning(
                "failed to inject IKP rules for pack %r", pack_name,
                exc_info=True,
            )
    return created


# ── External design repo helpers ────────────────────────────────────

_CSS_VAR_RE = re.compile(r"^\s*(--[\w-]+)\s*:\s*(.+?)\s*;", re.MULTILINE)


def _extract_css_tokens(globals_css_path: Path) -> dict[str, dict[str, str]]:
    """Extract CSS custom properties from globals.css.

    Returns {"light": {"--var": "value"}, "dark": {"--var": "value"}}.
    """
    result: dict[str, dict[str, str]] = {"light": {}, "dark": {}}
    if not globals_css_path.is_file():
        return result
    try:
        content = globals_css_path.read_text()
    except OSError:
        return result

    def _extract_block(text: str, start_pattern: str, target_key: str) -> None:
        idx = text.find(start_pattern)
        while idx >= 0:
            brace_start = text.find("{", idx)
            if brace_start < 0:
                break
            depth = 1
            pos = brace_start + 1
            while pos < len(text) and depth > 0:
                if text[pos] == "{":
                    depth += 1
                elif text[pos] == "}":
                    depth -= 1
                pos += 1
            block = text[brace_start + 1 : pos - 1]
            for m in _CSS_VAR_RE.finditer(block):
                result[target_key][m.group(1)] = m.group(2)
            idx = text.find(start_pattern, pos)

    _extract_block(content, ":root", "light")
    _extract_block(content, ".dark", "dark")

    return result


def _format_design_tokens(tokens: dict[str, dict[str, str]]) -> str:
    """Format extracted CSS tokens as markdown."""
    if not tokens["light"] and not tokens["dark"]:
        return ""
    lines = ["## Design Tokens", ""]
    if tokens["light"]:
        lines.append("### Light Theme")
        for var, val in tokens["light"].items():
            lines.append(f"- `{var}`: `{val}`")
        lines.append("")
    if tokens["dark"]:
        lines.append("### Dark Theme")
        for var, val in tokens["dark"].items():
            lines.append(f"- `{var}`: `{val}`")
        lines.append("")
    return "\n".join(lines)


def _inject_external_design_rules(
    external_path: Path, wt_path: Path,
) -> int:
    """Symlink .set-designer/design-rules/*.md into worktree rules."""
    rules_src = external_path / ".set-designer" / "design-rules"
    if not rules_src.is_dir():
        logger.debug("no design rules at %s", rules_src)
        return 0

    rules_dst = wt_path / ".claude" / "rules"
    rules_dst.mkdir(parents=True, exist_ok=True)

    count = 0
    for md_file in sorted(rules_src.glob("*.md")):
        dst_name = f"design-{md_file.name}"
        dst_path = rules_dst / dst_name
        if dst_path.exists():
            logger.warning("design rule name collision: %s", dst_name)
            continue
        try:
            dst_path.symlink_to(md_file.resolve())
            count += 1
        except OSError:
            logger.warning("failed to symlink design rule %s", md_file.name, exc_info=True)

    if count:
        logger.info("injected %d external design rules from %s", count, rules_src)
    return count
