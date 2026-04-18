"""v0 fixture renderer: content substitution + headless build for screenshots.

Copies v0-export/ to a temp dir, patches it with HU content + mock data from
content-fixtures.yaml, runs pnpm install --frozen-lockfile && pnpm build &&
pnpm start, health-checks, and returns the base URL. The original v0-export/
is never mutated.

Used by the design-fidelity gate to render the v0 reference alongside the
agent's worktree for pixel-diff comparison.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

import yaml

logger = logging.getLogger(__name__)


NODE_CACHE_DIR = Path.home() / ".cache" / "set-orch" / "v0-node-modules"
NODE_CACHE_MAX_HASHES = 3

# Port range for concurrent gate runs.
PORT_RANGE_START = 3400
PORT_RANGE_END = 3499


class ReferenceBuildError(RuntimeError):
    """Raised when pnpm build of the v0 reference fails."""


class FixturesMissingError(RuntimeError):
    """Raised when fixtures are required but not provided."""


@dataclass
class Fixtures:
    string_replacements: dict[str, str] = field(default_factory=dict)
    mock_data: dict = field(default_factory=dict)
    data_imports: dict[str, str] = field(default_factory=dict)
    language: str = "en"


@dataclass
class RenderHandle:
    base_url: str
    port: int
    temp_dir: Path
    server_pid: int


# ─── Public API ─────────────────────────────────────────────────────


def load_fixtures(path: Path) -> Fixtures:
    """Load content-fixtures.yaml; empty file → empty Fixtures()."""
    if not path.is_file():
        raise FixturesMissingError(f"fixtures file not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    return Fixtures(
        string_replacements=dict(data.get("string_replacements") or {}),
        mock_data=dict(data.get("mock_data") or {}),
        data_imports=dict(data.get("data_imports") or {}),
        language=str(data.get("language", "en")),
    )


@contextmanager
def render_v0_with_fixtures(
    v0_export: Path,
    fixtures: Fixtures,
    health_timeout_seconds: int = 30,
) -> Iterator[RenderHandle]:
    """Context manager that yields a RenderHandle with base_url.

    On exit, terminates the server and removes the temp directory.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix=f"v0-render-{uuid.uuid4().hex[:8]}-"))
    server_pid: Optional[int] = None
    port = _allocate_port()
    try:
        logger.info("Rendering v0 reference in %s (port %d)", temp_dir, port)
        _copy_v0(v0_export, temp_dir)
        _apply_string_replacements(temp_dir, fixtures.string_replacements)
        _apply_data_imports(temp_dir, fixtures.data_imports)
        _install_and_build(temp_dir)
        server_pid = _start_server(temp_dir, port)
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url, health_timeout_seconds)
        yield RenderHandle(
            base_url=base_url, port=port, temp_dir=temp_dir, server_pid=server_pid,
        )
    finally:
        if server_pid is not None:
            _stop_server(server_pid)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


# ─── Internals ──────────────────────────────────────────────────────


def _copy_v0(v0_export: Path, dest: Path) -> None:
    """Copy v0-export to dest (dest must not exist yet)."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(v0_export, dest)


def _apply_string_replacements(root: Path, repls: dict[str, str]) -> None:
    """Replace literal strings across .tsx/.ts/.jsx/.js files in root."""
    if not repls:
        return
    exts = (".tsx", ".ts", ".jsx", ".js")
    zero_match: list[str] = []
    for needle, replacement in repls.items():
        replaced_any = False
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix not in exts:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            if needle not in text:
                continue
            f.write_text(text.replace(needle, replacement), encoding="utf-8")
            replaced_any = True
        if not replaced_any:
            zero_match.append(needle)
    if zero_match:
        logger.debug("string replacements with 0 matches: %s", zero_match)


def _apply_data_imports(root: Path, data_imports: dict[str, str]) -> None:
    """For each target_path → fixture_body mapping, overwrite the target."""
    for target, body in data_imports.items():
        target_path = root / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists():
            logger.info("data_imports creates new file %s", target_path)
        target_path.write_text(body, encoding="utf-8")


def _install_and_build(root: Path) -> None:
    """Run pnpm install --frozen-lockfile && pnpm build in root.

    Uses a copy-on-write-aware cached node_modules keyed by pnpm-lock hash
    when available. Cache entries are treated as read-only.
    """
    lockfile = root / "pnpm-lock.yaml"
    cached_modules: Optional[Path] = None
    if lockfile.is_file():
        hash_ = _hash_file(lockfile)
        cached_modules = NODE_CACHE_DIR / hash_
        if cached_modules.is_dir():
            logger.info("cache hit for node_modules (hash=%s)", hash_)
            _copy_cow(cached_modules, root / "node_modules")

    install_args = ["pnpm", "install"]
    if lockfile.is_file():
        install_args.append("--frozen-lockfile")
    if cached_modules and (root / "node_modules").is_dir():
        install_args.append("--prefer-offline")

    r = subprocess.run(install_args, cwd=root)
    if r.returncode != 0:
        raise ReferenceBuildError("pnpm install failed")

    # Populate cache on first miss.
    if lockfile.is_file() and cached_modules and not cached_modules.is_dir():
        NODE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        src = root / "node_modules"
        if src.is_dir():
            try:
                _copy_cow(src, cached_modules)
            except Exception:
                logger.debug("failed to populate node_modules cache", exc_info=True)
        _prune_node_cache()

    r = subprocess.run(["pnpm", "build"], cwd=root)
    if r.returncode != 0:
        raise ReferenceBuildError("pnpm build failed")


def _start_server(root: Path, port: int) -> int:
    """Start pnpm start in background on port; return PID."""
    env = os.environ.copy()
    env["PORT"] = str(port)
    # Detach: new session so we can signal the group later.
    proc = subprocess.Popen(
        ["pnpm", "start"],
        cwd=root, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return proc.pid


def _stop_server(pid: int) -> None:
    """SIGTERM → 5s → SIGKILL the process group."""
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    time.sleep(5)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass


def _wait_for_health(base_url: str, timeout_seconds: int) -> None:
    """Poll HTTP GET / until 200 or timeout."""
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout_seconds
    last_err: Optional[str] = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/", timeout=3) as r:
                if 200 <= r.status < 500:
                    logger.info("v0 reference server healthy at %s (status=%d)", base_url, r.status)
                    return
        except urllib.error.URLError as e:
            last_err = str(e)
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)
    raise ReferenceBuildError(
        f"v0 reference server at {base_url} did not respond within {timeout_seconds}s (last err: {last_err})"
    )


def _allocate_port() -> int:
    """Scan PORT_RANGE for a free port."""
    for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise ReferenceBuildError(
        f"no free port in range {PORT_RANGE_START}-{PORT_RANGE_END}"
    )


def _hash_file(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return h[:16]


def _copy_cow(src: Path, dst: Path) -> None:
    """Copy src→dst preferring cp --reflink=auto (CoW on supported FS)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["cp", "-a", "--reflink=auto", str(src) + "/.", str(dst)],
        capture_output=True,
    )
    if r.returncode != 0:
        # Fallback to shutil copytree
        shutil.copytree(src, dst, dirs_exist_ok=True)


def _prune_node_cache() -> None:
    if not NODE_CACHE_DIR.is_dir():
        return
    entries = [p for p in NODE_CACHE_DIR.iterdir() if p.is_dir()]
    if len(entries) <= NODE_CACHE_MAX_HASHES:
        return
    entries.sort(key=lambda p: p.stat().st_mtime)
    for p in entries[: len(entries) - NODE_CACHE_MAX_HASHES]:
        logger.info("LRU-pruning node_modules cache: %s", p)
        shutil.rmtree(p, ignore_errors=True)
