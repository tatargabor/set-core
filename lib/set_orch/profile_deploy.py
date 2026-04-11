from __future__ import annotations

"""Deploy template files from a project type package into a target project."""

import hashlib
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from .profile_types import ProjectType


@dataclass
class FileEntry:
    """A template file entry with optional deployment flags."""
    path: str
    protected: bool = False
    merge: bool = False


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

    # reflection.md → .set/reflection.md (agent learning file).
    # Lives in .set/ because Claude Code's sensitive-file policy blocks writes
    # under .claude/, which used to cause a permission-denial storm per agent
    # iteration (observed in craftbrew-run-20260421-0025: ~100 such events).
    if template_rel == "reflection.md":
        return target_dir / ".set" / "reflection.md"

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


def _parse_file_entry(raw: Any) -> FileEntry:
    """Parse a manifest entry into a FileEntry.

    Supports plain strings (backward compat) and dict objects with flags.
    """
    if isinstance(raw, str):
        return FileEntry(path=raw)
    if isinstance(raw, dict):
        return FileEntry(
            path=raw.get("path", ""),
            protected=bool(raw.get("protected", False)),
            merge=bool(raw.get("merge", False)),
        )
    return FileEntry(path=str(raw))


def _resolve_file_list(
    template_dir: Path,
    manifest: Optional[Dict[str, Any]],
    modules: Optional[List[str]],
) -> Tuple[List[FileEntry], List[str]]:
    """Resolve the list of template files to deploy.

    Returns (file_entries, warnings).
    Supports both plain string entries and dict entries with protected/merge flags.
    """
    warns: List[str] = []

    if manifest is None:
        # No manifest — deploy all files (backward compat), skip manifest itself
        entries: List[FileEntry] = []
        for src in sorted(template_dir.rglob("*")):
            if src.is_dir():
                continue
            rel = str(src.relative_to(template_dir))
            if rel == "manifest.yaml":
                continue
            entries.append(FileEntry(path=rel))
        return entries, warns

    # Build entry list from core + selected modules
    raw_entries: List[Any] = list(manifest.get("core", []))

    available_modules = manifest.get("modules", {})
    if modules:
        for mid in modules:
            if mid not in available_modules:
                names = ", ".join(available_modules.keys())
                warns.append(f"Unknown module '{mid}'. Available: {names}")
                continue
            mod_files = available_modules[mid].get("files", [])
            raw_entries.extend(mod_files)

    # Parse, deduplicate, and validate
    seen: set = set()
    validated: List[FileEntry] = []
    for raw in raw_entries:
        entry = _parse_file_entry(raw)
        if not entry.path or entry.path in seen:
            continue
        seen.add(entry.path)
        src = template_dir / entry.path
        if not src.exists():
            warns.append(f"Manifest references missing file: {entry.path}")
        else:
            validated.append(entry)

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


def _file_matches_template(dst: Path, src: Path) -> bool:
    """Check if an existing file has identical content to the template (SHA256)."""
    try:
        dst_hash = hashlib.sha256(dst.read_bytes()).hexdigest()
        src_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        return dst_hash == src_hash
    except OSError:
        return False


def _merge_yaml_additive(existing_path: Path, template_path: Path) -> bool:
    """Merge template YAML into existing file additively.

    Adds keys from template that are missing in existing. Never overwrites
    existing keys. Returns True if file was modified.
    """
    if yaml is None:
        warnings.warn("PyYAML not installed — cannot merge YAML")
        return False
    try:
        with open(existing_path) as f:
            existing = yaml.safe_load(f) or {}
        with open(template_path) as f:
            template = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as e:
        warnings.warn(f"Failed to load YAML for merge: {e}")
        return False

    if not isinstance(existing, dict) or not isinstance(template, dict):
        return False

    added = False
    for key, value in template.items():
        if key not in existing:
            existing[key] = value
            added = True

    if added:
        with open(existing_path, "w") as f:
            yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return added


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

    File deployment respects manifest flags:
    - protected: skip if file exists and differs from template (project modified it)
    - merge: additive YAML merge (add missing keys, never overwrite existing)
    - inherits: deploy parent template first (e.g., mobile inherits web's nextjs)
    """
    resolved_id, template_dir = resolve_template(project_type, template_id)
    manifest = _load_manifest(template_dir)

    # Deploy parent template first if manifest declares inheritance
    if manifest and manifest.get("inherits"):
        parent_template_id = manifest["inherits"]
        parent_dir = project_type.get_template_dir(parent_template_id)
        if parent_dir and parent_dir.is_dir():
            parent_msgs = _deploy_single_template(
                parent_dir, target_dir, modules=None, force=force, dry_run=dry_run
            )
            # Return parent messages followed by child messages
            messages = parent_msgs
        else:
            messages = [f"  Warning: inherited template '{parent_template_id}' not found"]
    else:
        messages = []

    # Deploy the leaf template (with modules and optional-module display)
    leaf_msgs = _deploy_single_template(
        template_dir, target_dir, modules=modules, force=force, dry_run=dry_run
    )
    messages.extend(leaf_msgs)

    # Project-level template override: .claude/project-templates/
    project_templates = target_dir / ".claude" / "project-templates"
    if project_templates.is_dir():
        pt_messages = _merge_project_templates(project_templates, target_dir, force, dry_run)
        if pt_messages:
            messages.append("")
            messages.append("  Project-level template overrides:")
            messages.extend(pt_messages)

    return messages


def _deploy_single_template(
    template_dir: Path,
    target_dir: Path,
    modules: Optional[List[str]] = None,
    force: bool = False,
    dry_run: bool = False,
) -> List[str]:
    """Deploy files from a single template directory into the target."""
    manifest = _load_manifest(template_dir)
    messages: List[str] = []

    file_entries, warns = _resolve_file_list(template_dir, manifest, modules)

    for w in warns:
        messages.append(f"  Warning: {w}")

    # Deploy files
    for entry in file_entries:
        src_path = template_dir / entry.path
        dst = _target_path(entry.path, target_dir)

        if dst.exists() and not force:
            messages.append(f"  Skipped (exists): {dst.relative_to(target_dir)}")
            continue

        # Handle merge-mode files (additive YAML merge)
        if entry.merge and dst.exists():
            if dry_run:
                messages.append(f"  Would merge: {dst.relative_to(target_dir)}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                modified = _merge_yaml_additive(dst, src_path)
                verb = "Merged" if modified else "Merged (no new keys)"
                messages.append(f"  {verb}: {dst.relative_to(target_dir)}")
            continue

        # Handle protected files (skip if project has modified them)
        if entry.protected and force and dst.exists():
            if not _file_matches_template(dst, src_path):
                messages.append(
                    f"  Skipped (protected): {dst.relative_to(target_dir)}"
                )
                continue
            # Content matches template — safe to overwrite

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


def _merge_project_templates(
    templates_dir: Path,
    target_dir: Path,
    force: bool = False,
    dry_run: bool = False,
) -> List[str]:
    """Merge project-level template overrides on top of module templates.

    Files in .claude/project-templates/ are mapped through _target_path()
    and deployed to the target directory, overwriting module template files.
    """
    messages: List[str] = []
    for src in sorted(templates_dir.rglob("*")):
        if src.is_dir():
            continue
        rel = str(src.relative_to(templates_dir))
        dst = _target_path(rel, target_dir)

        verb = "Would deploy" if dry_run else "Deployed"
        if dst.exists():
            verb = "Would overwrite" if dry_run else "Overwritten"

        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        messages.append(f"    [project-template] {verb}: {dst.relative_to(target_dir)}")

    return messages
