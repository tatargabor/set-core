"""v0.app export importer (web module).

Materializes a v0.app Next.js export into a scaffold's v0-export/ directory
from one of two sources:
  - git repo (primary): `v0-git` — works with any provider via system git auth
  - ZIP file (fallback): `v0-zip` — offline / air-gapped

After materialization, generates <scaffold>/docs/design-manifest.yaml. The
dispatcher later symlinks v0-export/ into each worktree so agents read the
full design tree in-place (including app/globals.css) — no duplicate
globals.css sync is needed.

Per design D8: when a design source is declared, every operation must
succeed or hard-fail. No silent fallbacks.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


V0_REQUIRED_DIRS = ("app",)
V0_REQUIRED_FILES = ("package.json",)

# Cache root for cloned v0 repos. Hashed by URL so credentials embedded in
# URLs don't leak via directory names. LRU pruned at this cap.
CLONE_CACHE_DIR = Path.home() / ".cache" / "set-orch" / "v0-clones"
CLONE_CACHE_MAX_ENTRIES = 5


class V0ImportError(RuntimeError):
    """Raised when a v0 import fails validation or materialization."""


@dataclass
class ImportSummary:
    scaffold: Path
    v0_export_dir: Path
    manifest_path: Path
    source_type: str  # "v0-git" | "v0-zip"
    source_spec: str  # url@ref or zip path
    resolved_ref: Optional[str] = None  # SHA for git mode


# ─── Public API ─────────────────────────────────────────────────────


def import_v0_zip(
    source: Path,
    scaffold: Path,
    force: bool = False,
) -> ImportSummary:
    """Import a v0 export from a ZIP file into <scaffold>/v0-export/.

    Extracts, validates structure, syncs globals.css, generates manifest.
    Idempotent with --force: removes previous v0-export/ before extraction.
    """
    source = Path(source).resolve()
    scaffold = Path(scaffold).resolve()
    if not source.is_file():
        raise V0ImportError(f"source ZIP not found: {source}")

    v0_dir = scaffold / "v0-export"
    if v0_dir.exists():
        if not force:
            raise V0ImportError(
                f"v0-export/ already exists at {v0_dir}. Use --force to re-import."
            )
        logger.info("Removing existing v0-export/ at %s (--force)", v0_dir)
        shutil.rmtree(v0_dir)
    v0_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting %s → %s", source, v0_dir)
    with zipfile.ZipFile(source) as zf:
        zf.extractall(v0_dir)

    # Some ZIPs wrap the tree under a single top-level dir. Detect and unwrap.
    _flatten_single_toplevel(v0_dir)

    _validate_v0_structure(v0_dir, scaffold)

    from .v0_manifest import generate_manifest_from_tree

    manifest_path = scaffold / "docs" / "design-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    generate_manifest_from_tree(v0_dir, manifest_path)

    return ImportSummary(
        scaffold=scaffold,
        v0_export_dir=v0_dir,
        manifest_path=manifest_path,
        source_type="v0-zip",
        source_spec=str(source),
    )


def import_v0_git(
    repo_url: str,
    ref: str,
    scaffold: Path,
    force: bool = False,
) -> ImportSummary:
    """Import a v0 export from a git repo into <scaffold>/v0-export/.

    Works with any provider (GitHub/GitLab/Bitbucket/self-hosted). Delegates
    auth to system git (SSH agent, credential helper, PAT env vars). Caches
    clones at ~/.cache/set-orch/v0-clones/<sha256-of-url>/ with LRU prune.
    """
    scaffold = Path(scaffold).resolve()

    if _url_has_embedded_credentials(repo_url):
        logger.warning(
            "Repo URL appears to embed credentials — recommend SSH key or GITHUB_TOKEN env var instead. url=%s",
            _mask_url(repo_url),
        )

    cache_dir = _resolve_clone_cache(repo_url)
    resolved_sha = _clone_or_fetch(repo_url, ref, cache_dir)

    v0_dir = scaffold / "v0-export"
    if v0_dir.exists():
        if not force:
            raise V0ImportError(
                f"v0-export/ already exists at {v0_dir}. Use --force to re-import."
            )
        logger.info("Removing existing v0-export/ at %s (--force)", v0_dir)
        shutil.rmtree(v0_dir)
    v0_dir.mkdir(parents=True, exist_ok=True)

    # Materialize cache → scaffold/v0-export/, excluding .git/.
    _copy_tree_excluding_git(cache_dir, v0_dir)

    _validate_v0_structure(v0_dir, scaffold)

    from .v0_manifest import generate_manifest_from_tree

    manifest_path = scaffold / "docs" / "design-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    generate_manifest_from_tree(v0_dir, manifest_path)

    _prune_clone_cache()

    return ImportSummary(
        scaffold=scaffold,
        v0_export_dir=v0_dir,
        manifest_path=manifest_path,
        source_type="v0-git",
        source_spec=f"{repo_url}@{ref}",
        resolved_ref=resolved_sha,
    )


# ─── Internals: validation ──────────────────────────────────────────


def _validate_v0_structure(v0_dir: Path, scaffold: Path) -> None:
    """Validate that v0_dir contains an App Router export.

    Required: app/ directory, package.json. When the scaffold uses shadcn,
    components/ui/ is also required (hard fail per D8).
    """
    for d in V0_REQUIRED_DIRS:
        target = v0_dir / d
        if not target.is_dir():
            raise V0ImportError(
                f"v0 export missing required directory '{d}/' at {target}. "
                f"Is this a Next.js App Router export from v0.app?"
            )

    for f in V0_REQUIRED_FILES:
        target = v0_dir / f
        if not target.is_file():
            raise V0ImportError(f"v0 export missing required file '{f}' at {target}")

    # globals.css is REQUIRED — this is the token source of truth.
    globals_candidates = [
        v0_dir / "app" / "globals.css",
        v0_dir / "styles" / "globals.css",
    ]
    if not any(p.is_file() for p in globals_candidates):
        raise V0ImportError(
            f"v0 export missing globals.css (looked in app/ and styles/). "
            f"Design tokens cannot be extracted without it."
        )

    ui_library = _scaffold_ui_library(scaffold)
    ui_dir = v0_dir / "components" / "ui"
    if ui_library == "shadcn" and not ui_dir.is_dir():
        raise V0ImportError(
            f"v0 export missing components/ui/ but scaffold declares ui_library=shadcn. "
            f"Either regenerate v0 with shadcn primitives or set ui_library=none in scaffold.yaml."
        )


def _scaffold_ui_library(scaffold: Path) -> str:
    """Read scaffold.yaml's ui_library field (default 'shadcn')."""
    sf = scaffold / "scaffold.yaml"
    if not sf.is_file():
        return "shadcn"  # assume shadcn when no scaffold.yaml
    try:
        import yaml

        data = yaml.safe_load(sf.read_text()) or {}
        return str(data.get("ui_library", "shadcn"))
    except Exception:
        logger.debug("failed to parse scaffold.yaml at %s", sf, exc_info=True)
        return "shadcn"


def _flatten_single_toplevel(root: Path) -> None:
    """If extraction produced a single wrapper dir, lift its contents into root."""
    entries = [p for p in root.iterdir() if not p.name.startswith(".")]
    if len(entries) != 1 or not entries[0].is_dir():
        return
    wrapper = entries[0]
    # If the wrapper contains the expected v0 shape, flatten.
    if not (wrapper / "app").is_dir() and not (wrapper / "package.json").is_file():
        return
    logger.info("Flattening single wrapper directory %s", wrapper.name)
    for child in list(wrapper.iterdir()):
        shutil.move(str(child), str(root / child.name))
    wrapper.rmdir()


# ─── Internals: git clone cache ─────────────────────────────────────


def _resolve_clone_cache(repo_url: str) -> Path:
    """Return (and ensure parent exists) the cache dir for this repo URL."""
    digest = hashlib.sha256(repo_url.encode("utf-8")).hexdigest()[:16]
    CLONE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CLONE_CACHE_DIR / digest


def _clone_or_fetch(repo_url: str, ref: str, cache_dir: Path) -> str:
    """Clone (partial) or fetch + checkout ref. Return resolved SHA."""
    if not cache_dir.exists():
        logger.info("Cloning %s → %s (partial, no blobs)", _mask_url(repo_url), cache_dir)
        _run_git(
            [
                "clone",
                "--no-tags",
                "--filter=blob:none",
                repo_url,
                str(cache_dir),
            ]
        )
        # The partial clone with `--filter=blob:none` only fetches the default
        # branch's HEAD. If ref isn't the default branch, the ref isn't
        # locally resolvable yet. Fetch the specific ref explicitly so
        # `_resolve_remote_ref` (which tries `origin/<ref>`) can succeed.
        # Tolerate failure: ref may be a SHA already in the default-branch
        # history, in which case the explicit fetch is a no-op.
        try:
            _run_git(
                [
                    "-C", str(cache_dir),
                    "fetch", "--no-tags", "--filter=blob:none",
                    "origin",
                    f"+refs/heads/{ref}:refs/remotes/origin/{ref}",
                ]
            )
        except subprocess.CalledProcessError:
            # ref isn't a branch name (likely a SHA or tag) — try fetching
            # by SHA instead (tags are already covered by --no-tags=false elsewhere)
            try:
                _run_git(
                    [
                        "-C", str(cache_dir),
                        "fetch", "--no-tags", "--filter=blob:none",
                        "origin", ref,
                    ]
                )
            except subprocess.CalledProcessError:
                logger.debug("explicit fetch of ref %s failed; will rely on default-branch contents", ref)
        _write_cache_meta(cache_dir, repo_url)
    else:
        logger.info("Cache hit for %s; fetching", _mask_url(repo_url))
        _run_git(["-C", str(cache_dir), "fetch", "--no-tags", "--prune", "origin"])

    _run_git(["-C", str(cache_dir), "checkout", "--detach", _resolve_remote_ref(cache_dir, ref)])
    resolved = _run_git(
        ["-C", str(cache_dir), "rev-parse", "HEAD"], capture=True
    ).strip()

    # Warn if ref points to non-tip of a moving branch
    try:
        branch_head = _run_git(
            ["-C", str(cache_dir), "rev-parse", f"origin/{ref}"], capture=True
        ).strip()
        if branch_head and branch_head != resolved:
            logger.warning(
                "ref %s resolved to %s but origin/%s is at %s (ref is not at branch tip)",
                ref, resolved, ref, branch_head,
            )
    except subprocess.CalledProcessError:
        # ref is a tag or SHA — not a branch; no tip to compare
        pass

    # touch directory for LRU
    os.utime(cache_dir, None)
    return resolved


def _resolve_remote_ref(cache_dir: Path, ref: str) -> str:
    """Resolve ref to a checkout-friendly form. Branches → origin/<branch>."""
    # If it's already a SHA or tag, `git rev-parse --verify <ref>^{commit}` works.
    # `git rev-parse --verify` exits 128 for an unknown ref — that's the
    # NORMAL signal we should fall through to origin/<ref>, NOT an auth error.
    # `_run_git` reflexively converts exit 128 to V0ImportError, so we catch
    # both that and the underlying CalledProcessError.
    try:
        return _run_git(
            ["-C", str(cache_dir), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture=True,
        ).strip()
    except (subprocess.CalledProcessError, V0ImportError):
        pass
    # Otherwise try origin/<ref>
    try:
        return _run_git(
            ["-C", str(cache_dir), "rev-parse", "--verify", f"origin/{ref}^{{commit}}"],
            capture=True,
        ).strip()
    except (subprocess.CalledProcessError, V0ImportError) as e:
        raise V0ImportError(f"ref '{ref}' not found in clone of {cache_dir}") from e


def _write_cache_meta(cache_dir: Path, repo_url: str) -> None:
    meta = cache_dir / ".set-orch-meta"
    meta.write_text(f"url={_mask_url(repo_url)}\n")


def _prune_clone_cache() -> None:
    """LRU prune the clone cache to CLONE_CACHE_MAX_ENTRIES."""
    if not CLONE_CACHE_DIR.is_dir():
        return
    entries = [p for p in CLONE_CACHE_DIR.iterdir() if p.is_dir()]
    if len(entries) <= CLONE_CACHE_MAX_ENTRIES:
        return
    entries.sort(key=lambda p: p.stat().st_mtime)
    to_evict = entries[: len(entries) - CLONE_CACHE_MAX_ENTRIES]
    for p in to_evict:
        logger.info("LRU-pruning v0 clone cache: %s", p)
        shutil.rmtree(p, ignore_errors=True)


def _copy_tree_excluding_git(src: Path, dst: Path) -> None:
    """Copy src → dst, skipping .git/ directory."""

    def _ignore(_root: str, names: list[str]) -> list[str]:
        return [n for n in names if n == ".git"]

    # shutil.copytree requires dst to NOT already exist; caller already cleaned.
    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)


def _run_git(args: list[str], capture: bool = False) -> str:
    cmd = ["git", *args]
    try:
        if capture:
            out = subprocess.run(
                cmd, capture_output=True, text=True, check=True,
            )
            return out.stdout
        subprocess.run(cmd, check=True)
        return ""
    except subprocess.CalledProcessError as e:
        if e.returncode == 128:
            # Clone auth failure — actionable message.
            url = args[-1] if args else "<unknown>"
            raise V0ImportError(
                f"git operation exit 128 (typically auth failure) for {_mask_url(url)}.\n"
                f"Options to fix:\n"
                f"  1. SSH: ensure ssh-agent has a key with access (ssh-add -l)\n"
                f"  2. HTTPS + PAT: export GITHUB_TOKEN=<pat> (or set GitLab/Bitbucket equivalent)\n"
                f"  3. Credential helper: configure git config --global credential.helper\n"
                f"  4. Deploy key: add the repo's deploy key to ~/.ssh/\n"
                f"See docs/design-pipeline.md § 'Authentication for private design repos'."
            ) from e
        raise


def _mask_url(url: str) -> str:
    """Strip embedded credentials (https://user:pass@host/...) for logging."""
    import re
    return re.sub(r"https://[^@/]+@", "https://", url)


def _url_has_embedded_credentials(url: str) -> bool:
    """True if URL looks like https://user:pass@host/..."""
    import re
    return bool(re.match(r"https?://[^/]+@", url))
