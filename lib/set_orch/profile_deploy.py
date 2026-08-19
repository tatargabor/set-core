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

from .deploy_ledger import DeployLedger
from .module_install import perform_announcement, read_install_record
from .module_declaration import (
    DeclarationError,
    compare_generator_stamps,
    load_declaration,
    read_generator_stamp,
    validate_declaration,
)
from .profile_types import ProjectType


@dataclass
class FileEntry:
    """A template file entry with optional deployment flags.

    Two kinds of file live in a template, and they want opposite treatment once a
    project is real:

    - **Scaffold** (`once: true`) — starter code and config: a Prisma client stub,
      a lint config, an i18n catalogue seed. Written to get a project moving, then
      outgrown. Re-deploying it into a live project is never wanted, even when the
      project has not touched it; if such a file ever genuinely needs to move
      forward, that is an upgrade step with its own reasoning, not a side effect
      of `init`.
    - **Knowledge** (default) — the framework's own rules and conventions. These
      SHOULD keep flowing, or fixes never reach the projects that need them. The
      install ledger decides safely: untouched files update, edited ones do not.

    `protected` is a weaker, orthogonal guard: skip when the file exists and
    differs. It cannot tell "the project edited it" from "the template moved on",
    which is exactly why `once` and the ledger exist.
    """
    path: str
    protected: bool = False
    merge: bool = False
    once: bool = False


@dataclass
class FileOutcome:
    """What the deploy engine did with ONE file, as data rather than as a sentence.

    The engine has always reported per-file results as human prose — `"  Skipped
    (protected): x"` — and that is what its callers print. A second caller now needs
    the same facts to build a structured report for a screen, and the tempting shortcut
    is to parse the sentences back. That would be a parser over human-facing text,
    which is a defect class this repository has already paid for: an example read as an
    instruction, a rule quoted before a verdict read as the verdict.

    So the outcome is produced first and the sentence is rendered FROM it. The prose is
    unchanged byte for byte — including its two inconsistencies, which are preserved
    deliberately rather than tidied: `exists` and `protected` say "Skipped" even in a
    dry run, where every other skip says "Would skip". Fixing them here would change
    `set-project init`'s output in a change about something else.

    `action` is one of: `deployed`, `overwritten`, `unchanged`, `merged`, `skipped`,
    `warning`. `reason` is the parenthetical the engine already states, verbatim, so
    the vocabulary has exactly one owner.
    """
    action: str
    #: Target-relative path. Absent for `warning`, which is about the manifest.
    path: Optional[str] = None
    reason: Optional[str] = None
    #: The message the engine printed for this outcome — kept so the rendering and the
    #: data can never drift apart in a caller that shows both.
    message: str = ""
    dry_run: bool = False


def _outcome(sink: Optional[List[FileOutcome]], messages: List[str], *,
             action: str, message: str, path: Optional[str] = None,
             reason: Optional[str] = None, dry_run: bool = False) -> None:
    """Record one file's result in both forms, in one place.

    Both, always, from a single call — a helper that appended to only one of them would
    be a second place for the two to diverge, and the divergence would be silent in
    whichever form the reader is not looking at.
    """
    messages.append(message)
    if sink is not None:
        sink.append(FileOutcome(action=action, path=path, reason=reason,
                                message=message, dry_run=dry_run))


# Map template-relative paths to target-relative paths
_PATH_MAPPINGS: Dict[str, str] = {
    "rules/": ".claude/rules/",
    "framework-rules/": ".claude/rules/",
}

# Paths under these prefixes get a "set-" filename prefix when deployed
_SET_PREFIX_PATHS = ("framework-rules/",)


class ManifestValidationError(ValueError):
    """A module's declaration is incomplete or names a guard the installer cannot apply.

    Raised **before** anything is written. Every error is carried, not just the first: a
    manifest with three untreated entries should be fixable in one pass, not three.
    """

    def __init__(self, manifest_path: Path, errors: "List[DeclarationError]") -> None:
        self.manifest_path = manifest_path
        self.errors = list(errors)
        detail = "\n  ".join(str(e) for e in self.errors)
        super().__init__(
            f"{manifest_path} cannot be installed — {len(self.errors)} declaration "
            f"error(s):\n  {detail}"
        )


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
            once=bool(raw.get("once", False)),
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

    # A manifest may name its protected paths in a top-level list instead of flagging each
    # entry — two templates do, and until this was added NOBODY READ THAT LIST. The manifest
    # declared a guard that did not exist, which is the reassuring direction: the file said
    # `protected: [capacitor.config.ts]` and a forced re-init overwrote it anyway.
    #
    # Read as a SET of paths and applied below, so both spellings mean the same thing. The
    # per-entry flag still wins where both appear — it is the more specific statement.
    declared_protected = {
        str(p) for p in (manifest.get("protected") or []) if isinstance(p, (str, int))
    }

    # NOTE on `executable:`, kept because the obvious "fix" here is wrong and was written
    # once already. This parser does not know the key, and it does not need to: a path
    # declared BOTH as the module's executable part and as an installed file is **refused**
    # by `validate_declaration`, which runs above this call — so the only input that could
    # separate this reader from `plan_files` never reaches it. Adding an exclusion here
    # would be unreachable code claiming to be a guard, which is the shape this repository
    # has already been bitten by from the other side (a manifest that declared a protection
    # nothing read). The guarantee is the refusal; see `test_a_manifest_that_declares_a_path
    # _as_both_is_refused_by_the_deploy_path`.

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
        # The top-level list only ever ADDS protection. It cannot clear a per-entry flag,
        # because a manifest that says `protected: true` on an entry has already made the
        # more specific statement, and a broad list quietly cancelling it would be the
        # opposite of what either spelling looks like it means.
        if entry.path in declared_protected:
            entry.protected = True
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

    # One ledger for the whole pass: parent, leaf and project-level overrides all
    # record into it, and it is written once at the end.
    ledger = DeployLedger.load(target_dir)

    # Deploy parent template first if manifest declares inheritance
    if manifest and manifest.get("inherits"):
        parent_template_id = manifest["inherits"]
        parent_dir = project_type.get_template_dir(parent_template_id)
        if parent_dir and parent_dir.is_dir():
            parent_msgs = _deploy_single_template(
                parent_dir, target_dir, modules=None, force=force, dry_run=dry_run,
                ledger=ledger,
            )
            # Return parent messages followed by child messages
            messages = parent_msgs
        else:
            messages = [f"  Warning: inherited template '{parent_template_id}' not found"]
    else:
        messages = []

    # Deploy the leaf template (with modules and optional-module display)
    leaf_msgs = _deploy_single_template(
        template_dir, target_dir, modules=modules, force=force, dry_run=dry_run,
        ledger=ledger,
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

    if not dry_run:
        ledger.save()

    tombstoned = sorted(ledger.tombstones)
    if tombstoned:
        messages.append("")
        messages.append(
            f"  {len(tombstoned)} path(s) not deployed — removed by the project "
            f"(clear the entry in set/.deploy-manifest.json to restore):"
        )
        messages.extend(f"    - {t}" for t in tombstoned)

    return messages


def _deploy_single_template(
    template_dir: Path,
    target_dir: Path,
    modules: Optional[List[str]] = None,
    force: bool = False,
    dry_run: bool = False,
    ledger: Optional["DeployLedger"] = None,
    outcomes: Optional[List[FileOutcome]] = None,
) -> List[str]:
    """Deploy files from a single template directory into the target."""
    manifest = _load_manifest(template_dir)
    messages: List[str] = []

    # A declared guard that does not take effect is an error, not silence. This repository
    # has already shipped the opposite: two templates named their protected paths in a
    # top-level list that nothing read, so the manifest promised a protection the installer
    # never applied and a forced re-init overwrote the file anyway. Validating here — before
    # a single byte is written — is what turns the declaration into something in force rather
    # than something stated.
    #
    # A template with NO manifest is a different case and is left alone: the legacy path
    # deploys everything, and refusing it would break projects that never declared anything.
    if manifest is not None:
        decl = load_declaration(
            manifest, name=template_dir.name, source=template_dir / "manifest.yaml",
            modules=modules,
        )
        errors = validate_declaration(decl, template_dir=template_dir)
        if errors:
            raise ManifestValidationError(template_dir / "manifest.yaml", errors)

    owns_ledger = ledger is None
    if ledger is None:
        ledger = DeployLedger.load(target_dir)

    file_entries, warns = _resolve_file_list(template_dir, manifest, modules)

    for w in warns:
        _outcome(outcomes, messages, action="warning", reason=w,
                 message=f"  Warning: {w}", dry_run=dry_run)

    # Deploy files
    for entry in file_entries:
        src_path = template_dir / entry.path
        dst = _target_path(entry.path, target_dir)
        key = ledger.rel_key(dst)
        # Computed once. It was `dst.relative_to(target_dir)` inline at nine call sites,
        # which is nine chances for one of them to render a path differently from the
        # data beside it.
        rel = str(dst.relative_to(target_dir))

        # Tombstone: the project deployed this once and then deleted it. Re-creating
        # it would re-arm content the project deliberately removed, so never do it
        # implicitly — the ledger's `tombstones` entry must be dropped by hand first.
        if ledger.is_tombstoned(key):
            verb = "Would skip" if dry_run else "Skipped"
            _outcome(outcomes, messages, action="skipped", path=rel,
                     reason="removed by project", dry_run=dry_run,
                     message=f"  {verb} (removed by project): {rel}")
            continue

        # Neither absence rule below applies to a path git currently ignores. Absence
        # proves nothing there — `git clean -fdx` removes it and so does every fresh
        # clone — and a deletion in its history is about the era when it WAS tracked,
        # not about today. Measured: `.set/reflection.md` is ignored because the agent
        # learning file had to move out of `.claude/`; that move is in history as a
        # deletion, and reading it as intent retired the file for good.
        absent_without_intent = not dst.exists() and ledger.is_git_ignored(key)

        # Absent, but we deployed it before → the project removed it. Record the
        # tombstone now so the next run is decided by history, not by chance.
        if not dst.exists() and key in ledger.files and not absent_without_intent:
            if not dry_run:
                ledger.tombstone(key)
            verb = "Would skip" if dry_run else "Skipped"
            _outcome(outcomes, messages, action="skipped", path=rel,
                     reason="deleted by project, tombstoned", dry_run=dry_run,
                     message=f"  {verb} (deleted by project, tombstoned): {rel}")
            continue

        # Absent and unknown to the ledger. On a first init that describes both a
        # genuinely new file and one the project deleted years ago, and the ledger
        # cannot separate them — but the project's git history can.
        if not dst.exists() and not absent_without_intent and ledger.deleted_in_history(key):
            if not dry_run:
                ledger.tombstone(key, source="git history")
            verb = "Would skip" if dry_run else "Skipped"
            _outcome(outcomes, messages, action="skipped", path=rel,
                     reason="deleted in git history, tombstoned", dry_run=dry_run,
                     message=f"  {verb} (deleted in git history, tombstoned): {rel}")
            continue

        if dst.exists() and not force:
            _outcome(outcomes, messages, action="skipped", path=rel,
                     reason="exists", dry_run=dry_run,
                     message=f"  Skipped (exists): {rel}")
            continue

        # Handle merge-mode files (additive YAML merge)
        if entry.merge and dst.exists():
            if dry_run:
                _outcome(outcomes, messages, action="merged", path=rel, dry_run=True,
                         message=f"  Would merge: {rel}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                modified = _merge_yaml_additive(dst, src_path)
                verb = "Merged" if modified else "Merged (no new keys)"
                _outcome(outcomes, messages, action="merged", path=rel,
                         reason=None if modified else "no new keys",
                         message=f"  {verb}: {rel}")
            continue

        # Scaffold: written once to start a project, then owned by it. Present is
        # done — do not re-deploy, and do not care whether it was edited. Moving a
        # scaffold file forward is an upgrade decision, never a side effect of init.
        if entry.once and dst.exists():
            verb = "Would skip" if dry_run else "Skipped"
            _outcome(outcomes, messages, action="skipped", path=rel,
                     reason="scaffold, already present", dry_run=dry_run,
                     message=f"  {verb} (scaffold, already present): {rel}")
            continue

        # Handle protected files (skip if project has modified them)
        identical = False
        if entry.protected and force and dst.exists():
            if not _file_matches_template(dst, src_path):
                _outcome(outcomes, messages, action="skipped", path=rel,
                         reason="protected", dry_run=dry_run,
                         message=f"  Skipped (protected): {rel}")
                continue
            # Content matches template — safe to overwrite
            identical = True

        # A generated artifact carries the version of the generator that produced it.
        # Replacing a newer one with an older generator's output is a downgrade, and it is
        # silent: the file still looks generated. Measured on this repository's own
        # `openspec update` path, where a 1.1.1 artifact would overwrite a 1.9.0 one.
        # A missing stamp on either side is unknown, and unknown leaves the destination
        # alone — the conservative direction, because an unstamped destination may be the
        # newer of the two.
        if dst.exists():
            stamp = compare_generator_stamps(
                entry.path,
                destination_stamp=read_generator_stamp(dst),
                incoming_stamp=read_generator_stamp(src_path),
            )
            if stamp.verdict == "refuse":
                verb = "Would skip" if dry_run else "Skipped"
                _outcome(outcomes, messages, action="skipped", path=rel,
                         reason=f"newer generator at destination — {stamp.reason}",
                         dry_run=dry_run,
                         message=(f"  {verb} (newer generator at destination): "
                                  f"{rel} — {stamp.reason}"))
                continue

        verb = "Would deploy" if dry_run else "Deployed"
        if dst.exists() and force:
            # Say what actually happens. Reporting a byte-identical rewrite as an
            # "overwrite" makes a no-op read as data loss, and a plan nobody trusts
            # is a plan nobody reads.
            if identical or _file_matches_template(dst, src_path):
                verb = "Unchanged (identical)"
            else:
                verb = "Would overwrite" if dry_run else "Overwritten"

        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst)
            # Record what we wrote so the next run can tell "project edited this"
            # from "the template moved on", and a later deletion becomes a tombstone.
            ledger.record(key, src_path)

        _outcome(
            outcomes, messages, path=rel, dry_run=dry_run,
            action=("unchanged" if verb.startswith("Unchanged")
                    else "overwritten" if "overwrite" in verb.lower()
                    else "deployed"),
            reason="identical" if verb.startswith("Unchanged") else None,
            message=f"  {verb}: {rel}",
        )

    # The announcement runs after the files, and only for a module that asked for one. It
    # is the same call on every path that announces, rather than a behaviour one entry point
    # happens to have — a behaviour only some entry points have is, statistically, a
    # behaviour the system does not have.
    # The record of what is installed here, written for EVERY module — not only for one
    # that happens to announce itself.
    #
    # Measured 2026-08-19: the only `record.save()` on this path sat inside the announce
    # branch below, so a module with no `announce:` section installed its files and left no
    # trace that it had. The consequence was visible three layers away: the capability
    # report has to fall back to inferring from file presence, and the fleet screen measured
    # **no declaration and 0 ledgered files across three real projects**. The record a
    # reader wants was one the framework never wrote.
    #
    # Written after the files and never on a dry run, so it cannot claim an install that
    # did not happen.
    if manifest is not None and not dry_run and decl.name:
        record = read_install_record(target_dir)
        record.modules[decl.name] = decl.version
        record.save(target_dir)

    if manifest is not None and decl.announce is not None:
        ann_msgs, written_body = perform_announcement(decl, target_dir, dry_run=dry_run)
        # The announcement edits a file the PROJECT owns, so it is a write like any
        # other and belongs in the outcomes. It is not one of the planned files, which
        # is exactly why it would otherwise be the one write no report mentions — and a
        # write nobody reports is the same class of defect as a skip nobody reports.
        for m in ann_msgs:
            _outcome(outcomes, messages, action="announced",
                     path=(decl.announce.file if decl.announce else None),
                     message=m, dry_run=dry_run)
        if written_body is not None and not dry_run:
            # Re-read rather than reuse the object above: `perform_announcement` may have
            # written the file, and the record is the durable statement about it. The
            # module line is already there from the block above; this adds the body.
            record = read_install_record(target_dir)
            record.announcements[decl.name] = written_body
            record.modules.setdefault(decl.name, decl.version)
            record.save(target_dir)

    if owns_ledger and not dry_run:
        ledger.save()

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
