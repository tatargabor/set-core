"""Web-specific post-merge operations.

Moved from lib/set_orch/merger.py as part of profile-driven-gate-registry.
Called via WebProjectType.post_merge_hooks().
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_i18n_sidecars(project_root: str = ".") -> int:
    """Merge i18n sidecar files into canonical message files.

    Scans for `<locale>.<namespace>.json` sidecar files in i18n message
    directories and merges them into the canonical `<locale>.json` at the
    top level (Object.assign semantics — no deep merge needed since each
    sidecar owns a unique top-level namespace).

    Returns the number of sidecar files merged.
    """
    msg_dirs = ["src/messages", "messages", "src/i18n/messages", "public/locales"]
    msg_dir = ""
    for d in msg_dirs:
        full = os.path.join(project_root, d)
        if os.path.isdir(full):
            msg_dir = full
            break

    if not msg_dir:
        return 0

    merged_count = 0
    for f in sorted(os.listdir(msg_dir)):
        if not f.endswith(".json"):
            continue
        parts = f.rsplit(".", 2)  # e.g. ["en", "checkout", "json"]
        if len(parts) != 3:
            continue
        locale, _namespace, _ext = parts

        sidecar_path = os.path.join(msg_dir, f)
        canonical_path = os.path.join(msg_dir, f"{locale}.json")

        try:
            sidecar_data = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("i18n sidecar: failed to read %s", sidecar_path)
            continue

        canonical_data: dict = {}
        if os.path.isfile(canonical_path):
            try:
                canonical_data = json.loads(Path(canonical_path).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                canonical_data = {}

        for key in sidecar_data:
            if key in canonical_data:
                logger.warning(
                    "i18n sidecar: namespace '%s' from %s already exists in %s — overwriting",
                    key, f, f"{locale}.json",
                )

        canonical_data.update(sidecar_data)

        try:
            Path(canonical_path).write_text(
                json.dumps(canonical_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.remove(sidecar_path)
            merged_count += 1
            logger.info("i18n sidecar: merged %s into %s.json", f, locale)
        except OSError:
            logger.warning("i18n sidecar: failed to write %s", canonical_path)

    # After merging sidecars, warn about bare imports that will crash
    if merged_count > 0:
        _warn_bare_sidecar_imports(project_root, msg_dir)

    return merged_count


def _warn_bare_sidecar_imports(project_root: str, msg_dir: str) -> None:
    """Warn if i18n request.ts has bare sidecar imports without try/catch.

    After sidecars are merged into canonical files and deleted, any bare
    import of the sidecar file will crash the Next.js dev server with
    'Cannot find module'. This check catches that before E2E tests run.
    """
    import re

    request_paths = [
        os.path.join(project_root, "src", "i18n", "request.ts"),
        os.path.join(project_root, "src", "i18n", "request.tsx"),
    ]
    request_file = ""
    for p in request_paths:
        if os.path.isfile(p):
            request_file = p
            break
    if not request_file:
        return

    try:
        content = Path(request_file).read_text(encoding="utf-8")
    except OSError:
        return

    # Look for sidecar-style imports (files with 2+ dots like "hu.feature.json")
    # that are NOT inside a try block
    sidecar_import_pattern = re.compile(
        r"""import\s+.*from\s+['"].*\.\w+\.json['"]"""
    )
    lines = content.split("\n")
    in_try = False
    bare_imports = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("try"):
            in_try = True
        if stripped.startswith("} catch") or stripped.startswith("catch"):
            in_try = False
        if sidecar_import_pattern.search(line) and not in_try:
            bare_imports.append((i, stripped))

    for lineno, line in bare_imports:
        logger.warning(
            "i18n sidecar: BARE IMPORT at %s:%d — will crash after archive. "
            "Wrap in try/catch: %s",
            request_file, lineno, line,
        )
