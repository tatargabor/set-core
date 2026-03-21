"""Deploy template files from a project type package into a target project."""

import shutil
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from .profile_types import ProjectType


# Map template-relative paths to target-relative paths
_PATH_MAPPINGS: Dict[str, str] = {
    "rules/": ".claude/rules/",
    "framework-rules/": ".claude/rules/",
}

# Paths under these prefixes get a "set-" filename prefix when deployed
_SET_PREFIX_PATHS = ("framework-rules/",)


def _target_path(template_rel: str, target_dir: Path) -> Path:
    """Map a template-relative path to the target directory location."""
    # project-knowledge.yaml → set/knowledge/ if it exists, else project root
    if template_rel == "project-knowledge.yaml":
        set_knowledge = target_dir / "set" / "knowledge"
        if set_knowledge.is_dir():
            return set_knowledge / template_rel
        return target_dir / template_rel

    # Apply path mappings (e.g., rules/ → .claude/rules/)
    for prefix, target_prefix in _PATH_MAPPINGS.items():
        if template_rel.startswith(prefix):
            rel_within = template_rel[len(prefix):]
            dst = Path(target_prefix) / rel_within
            # Framework rules get "set-" filename prefix
            if any(template_rel.startswith(p) for p in _SET_PREFIX_PATHS):
                dst = dst.parent / f"set-{dst.name}"
            return target_dir / dst

    # Default: same relative path
    return target_dir / template_rel


def _load_manifest(template_dir: Path) -> Optional[Dict[str, Any]]:
    """Load manifest.yaml from a template directory, or None if absent."""
    manifest_path = template_dir / "manifest.yaml"
    if not manifest_path.exists():
        return None
    if yaml is None:
        warnings.warn("PyYAML not installed — manifest.yaml not available")
        return None
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        warnings.warn(f"Failed to parse manifest.yaml: {e}")
        return None
    return data if isinstance(data, dict) else None


def get_available_modules(template_dir: Path) -> Dict[str, str]:
    """Return {module_id: description} for optional modules in a template.

    Returns empty dict if no manifest or no modules.
    """
    manifest = _load_manifest(template_dir)
    if not manifest or "modules" not in manifest:
        return {}
    modules = manifest.get("modules", {})
    return {mid: mdef.get("description", "") for mid, mdef in modules.items()}


def _resolve_file_list(
    template_dir: Path,
    manifest: Optional[Dict[str, Any]],
    modules: Optional[List[str]],
) -> Tuple[List[str], List[str]]:
    """Resolve the list of template-relative files to deploy.

    Returns (files_to_deploy, warnings).
    """
    warns: List[str] = []

    if manifest is None:
        # No manifest — deploy all files (backward compat), skip manifest itself
        files = []
        for src in sorted(template_dir.rglob("*")):
            if src.is_dir():
                continue
            rel = str(src.relative_to(template_dir))
            if rel == "manifest.yaml":
                continue
            files.append(rel)
        return files, warns

    # Build file list from core + selected modules
    files: List[str] = list(manifest.get("core", []))

    available_modules = manifest.get("modules", {})
    if modules:
        for mid in modules:
            if mid not in available_modules:
                names = ", ".join(available_modules.keys())
                warns.append(f"Unknown module '{mid}'. Available: {names}")
                continue
            mod_files = available_modules[mid].get("files", [])
            files.extend(mod_files)

    # Deduplicate (module file might already be in core) and validate
    seen: set = set()
    validated = []
    for rel in files:
        if rel in seen:
            continue
        seen.add(rel)
        src = template_dir / rel
        if not src.exists():
            warns.append(f"Manifest references missing file: {rel}")
        else:
            validated.append(rel)

    return validated, warns


def resolve_template(
    project_type: ProjectType,
    template_id: Optional[str] = None,
) -> Tuple[str, Path]:
    """Resolve which template to use, returning (template_id, template_dir).

    If template_id is None and only one template exists, auto-select it.
    Raises ValueError if template_id is needed but not provided, or if
    the specified template doesn't exist.
    """
    templates = project_type.get_templates()

    if not templates:
        raise ValueError(
            f"Project type '{project_type.info.name}' has no templates"
        )

    if template_id is None:
        if len(templates) == 1:
            template_id = templates[0].id
        else:
            names = ", ".join(t.id for t in templates)
            raise ValueError(
                f"Multiple templates available for '{project_type.info.name}': "
                f"{names}. Use --template <name> to select one."
            )

    template_dir = project_type.get_template_dir(template_id)
    if template_dir is None or not template_dir.is_dir():
        names = ", ".join(t.id for t in templates)
        raise ValueError(
            f"Unknown template '{template_id}' for project type "
            f"'{project_type.info.name}'. Available: {names}"
        )

    return template_id, template_dir


def deploy_templates(
    project_type: ProjectType,
    template_id: Optional[str],
    target_dir: Path,
    modules: Optional[List[str]] = None,
    force: bool = False,
    dry_run: bool = False,
) -> List[str]:
    """Deploy template files from a project type into the target directory.

    Returns a list of status messages for each file (deployed/skipped/overwritten).
    """
    resolved_id, template_dir = resolve_template(project_type, template_id)
    manifest = _load_manifest(template_dir)
    messages: List[str] = []

    file_list, warns = _resolve_file_list(template_dir, manifest, modules)

    for w in warns:
        messages.append(f"  Warning: {w}")

    # Deploy files
    for rel in file_list:
        src_path = template_dir / rel
        dst = _target_path(rel, target_dir)

        if dst.exists() and not force:
            messages.append(f"  Skipped (exists): {dst.relative_to(target_dir)}")
            continue

        verb = "Would deploy" if dry_run else "Deployed"
        if dst.exists() and force:
            verb = "Would overwrite" if dry_run else "Overwritten"

        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst)

        messages.append(f"  {verb}: {dst.relative_to(target_dir)}")

    # Show available optional modules if manifest exists and none were selected
    if manifest and not modules:
        available = manifest.get("modules", {})
        if available:
            messages.append("")
            messages.append("  Optional modules available:")
            for mid, mdef in available.items():
                desc = mdef.get("description", "")
                messages.append(f"    - {mid}: {desc}")
            messages.append("  Use --modules <name,...> to deploy optional modules")

    return messages
