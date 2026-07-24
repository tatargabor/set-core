from __future__ import annotations

"""Deploy provenance ledger — shared by both deploy engines.

set-core deploys into a consumer project from two engines: the bash one
(`lib/project/deploy.sh` — commands, skills, core rules, agents) and the Python one
(`profile_deploy.py` — manifest-driven template files). Both used to be *stateless*:
they compared only what is on disk right now, which cannot answer the two questions
that decide whether a redeploy is safe.

    1. "The file differs from the template — did the PROJECT edit it, or did the
       TEMPLATE move on since we deployed?" Without history, an engine must either
       overwrite (destroying consumer work) or never update (freezing the project).

    2. "The file is missing — is it NEW to this project, or did the project DELETE
       it on purpose?" Without history, every run resurrects deliberately removed
       files. Measured: a consumer deleted three `set-*` rules because their content
       had gone stale and wrong; a stateless deploy re-armed those false rules on
       every single init.

This module records what set-core actually wrote, in `<project>/set/.deploy-manifest.json`,
so both questions have a factual answer:

    files      — path → sha256 of the content we deployed
    tombstones — paths we deployed once and the project then removed

Decision table (`decide()`):

    tombstoned                        → SKIP  (project deleted it deliberately)
    dst missing, no ledger entry      → DEPLOY (genuinely new)
    dst missing, has ledger entry     → SKIP  + tombstone (project deleted it)
    dst exists, no ledger entry       → SKIP  (unknown provenance — never guess)
    dst exists, hash == recorded      → DEPLOY (untouched; the update lands)
    dst exists, hash != recorded      → SKIP  (the project owns it now)

The "unknown provenance" rule is what makes adoption safe on projects that predate
the ledger: the first run after this lands records nothing it did not verify, so no
pre-existing file is clobbered.

The bash engine writes the same schema (`lib/project/deploy_provenance.sh`); keep the
two in step.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

LEDGER_REL = os.path.join("set", ".deploy-manifest.json")
SCHEMA_VERSION = 2

_HELP = (
    "Written by `set-project init`. 'files' maps a project-relative path to the sha256 "
    "of the content set-core deployed there; a file whose hash still matches is treated "
    "as untouched and may be updated, one that differs belongs to the project and is left "
    "alone. 'tombstones' lists paths the project deleted on purpose — set-core will not "
    "recreate them. To accept the framework version of a tombstoned path again, remove its "
    "entry from the 'tombstones' list and re-run the init."
)


def sha256_file(path: Path) -> Optional[str]:
    """sha256 hex digest of a file, or None if it cannot be read."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        logger.debug("deploy_ledger: cannot hash %s: %s", path, exc)
        return None


class DeployLedger:
    """Provenance record for one consumer project.

    Load, consult during a deploy pass, then `save()`. A missing or corrupt ledger
    degrades to "know nothing", which makes every decision conservative (skip) rather
    than destructive — never let a bad ledger authorise an overwrite.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.path = self.project_root / LEDGER_REL
        self.files: Dict[str, str] = {}
        self.tombstones: Set[str] = set()
        self._dirty = False

    # ── loading ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, project_root: Path) -> "DeployLedger":
        ledger = cls(project_root)
        if not ledger.path.is_file():
            return ledger
        try:
            with open(ledger.path) as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning(
                "deploy_ledger: unreadable ledger at %s (%s) — treating as empty, "
                "every existing file will be preserved",
                ledger.path, exc,
            )
            return ledger

        if not isinstance(data, dict):
            logger.warning("deploy_ledger: ledger at %s is not an object — ignoring", ledger.path)
            return ledger

        raw_files = data.get("files")
        if isinstance(raw_files, dict):
            ledger.files = {
                k: v for k, v in raw_files.items()
                if isinstance(k, str) and isinstance(v, str)
            }
        raw_tombs = data.get("tombstones")
        if isinstance(raw_tombs, list):
            ledger.tombstones = {t for t in raw_tombs if isinstance(t, str)}
        return ledger

    # ── decisions ────────────────────────────────────────────────────────────

    def rel_key(self, dst: Path) -> str:
        """Project-relative, forward-slashed key for a destination path."""
        try:
            return Path(dst).resolve().relative_to(self.project_root.resolve()).as_posix()
        except ValueError:
            return Path(dst).as_posix()

    def is_tombstoned(self, key: str) -> bool:
        return key in self.tombstones

    def decide(self, key: str, dst: Path) -> Tuple[bool, str]:
        """Return (should_deploy, reason). Tombstones a path the project deleted."""
        if key in self.tombstones:
            return False, "removed by the project (tombstoned)"

        if not Path(dst).exists():
            if key in self.files:
                self.tombstone(key)
                return False, "deleted by the project — recorded as tombstone"
            return True, "new"

        known = self.files.get(key)
        if known is None:
            return False, "unknown provenance (predates the ledger)"

        current = sha256_file(Path(dst))
        if current is None:
            return False, "unreadable destination"
        if current == known:
            return True, "untouched since the last deploy"
        return False, "modified by the project"

    # ── mutations ────────────────────────────────────────────────────────────

    def record(self, key: str, src: Path) -> None:
        """Record the hash a destination carries after we copied `src` onto it."""
        digest = sha256_file(Path(src))
        if digest is None:
            return
        if self.files.get(key) != digest:
            logger.debug("deploy_ledger: record %s -> %s", key, digest[:12])
        self.files[key] = digest
        self.tombstones.discard(key)
        self._dirty = True

    def tombstone(self, key: str) -> None:
        """Mark a path as deliberately removed by the project."""
        if key in self.tombstones:
            return
        logger.info(
            "deploy_ledger: tombstoning %s — deployed previously, now absent; "
            "set-core will not recreate it", key,
        )
        self.tombstones.add(key)
        self.files.pop(key, None)
        self._dirty = True

    def untombstone(self, key: str) -> bool:
        """Explicit restore path: allow a tombstoned file to deploy again."""
        if key not in self.tombstones:
            return False
        self.tombstones.discard(key)
        self._dirty = True
        logger.info("deploy_ledger: untombstoned %s — it will deploy on the next run", key)
        return True

    # ── persistence ──────────────────────────────────────────────────────────

    def save(self) -> bool:
        """Write the ledger atomically. Returns True when something was written."""
        if not self._dirty:
            return False
        payload = {
            "version": SCHEMA_VERSION,
            "_help": _HELP,
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": dict(sorted(self.files.items())),
            "tombstones": sorted(self.tombstones),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with open(tmp, "w") as fh:
                json.dump(payload, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, self.path)
            logger.info(
                "deploy_ledger: wrote %s (%d file(s), %d tombstone(s))",
                self.path, len(self.files), len(self.tombstones),
            )
            self._dirty = False
            return True
        except OSError as exc:
            logger.warning("deploy_ledger: failed to write %s: %s", self.path, exc)
            return False


def tombstoned_paths(project_root: Path) -> List[str]:
    """Convenience read-only accessor for reporting."""
    return sorted(DeployLedger.load(Path(project_root)).tombstones)
