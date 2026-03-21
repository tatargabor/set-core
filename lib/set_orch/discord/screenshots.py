"""Screenshot attachment helpers for Discord threads.

Posts Playwright smoke/E2E screenshots to Discord threads with size
management and batching to respect Discord API limits.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 1_000_000  # 1MB — resize if larger
MAX_FILES_PER_MSG = 10  # Discord limit per message
MAX_TOTAL_SIZE = 25_000_000  # 25MB Discord limit per message


def _prepare_screenshots(paths: list[Path]) -> list[Path]:
    """Filter and optionally resize screenshots for Discord upload.

    Returns list of paths ready for upload (may include temp resized files).
    Skips files that exceed MAX_IMAGE_SIZE if Pillow is not available.
    """
    ready: list[Path] = []
    for p in paths:
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size <= MAX_IMAGE_SIZE:
            ready.append(p)
            continue

        # Try to resize with Pillow
        try:
            from PIL import Image
            img = Image.open(p)
            # Scale down to ~800px wide (good for Discord preview)
            if img.width > 800:
                ratio = 800 / img.width
                new_size = (800, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            # Save to temp path
            resized = p.parent / f"_discord_{p.name}"
            img.save(resized, optimize=True, quality=80)
            if resized.stat().st_size <= MAX_IMAGE_SIZE:
                ready.append(resized)
            else:
                logger.debug("Screenshot still too large after resize: %s", p.name)
                resized.unlink(missing_ok=True)
        except ImportError:
            logger.debug("Pillow not installed — skipping oversized screenshot: %s (%dKB)", p.name, size // 1024)
        except Exception as e:
            logger.debug("Failed to resize screenshot %s: %s", p.name, e)

    return ready


async def post_screenshots(
    thread: Any,
    paths: list[Path],
    caption: str = "",
    spoiler: bool = False,
) -> int:
    """Post screenshot files to a Discord thread.

    Batches into multiple messages if >10 files. Respects 25MB total limit.
    Returns number of screenshots posted.
    """
    import discord

    prepared = _prepare_screenshots(paths)
    if not prepared:
        return 0

    posted = 0
    # Batch into groups respecting file count and size limits
    batch: list[Path] = []
    batch_size = 0

    for p in prepared:
        fsize = p.stat().st_size
        if len(batch) >= MAX_FILES_PER_MSG or (batch_size + fsize) > MAX_TOTAL_SIZE:
            # Send current batch
            if batch:
                files = [discord.File(str(fp), filename=fp.name, spoiler=spoiler) for fp in batch]
                content = caption if posted == 0 else ""
                try:
                    await thread.send(content=content, files=files)
                    posted += len(batch)
                except discord.HTTPException as e:
                    logger.warning("Failed to post screenshots batch: %s", e)
                    break
            batch = []
            batch_size = 0

        batch.append(p)
        batch_size += fsize

    # Send remaining batch
    if batch:
        files = [discord.File(str(fp), filename=fp.name, spoiler=spoiler) for fp in batch]
        content = caption if posted == 0 else ""
        try:
            await thread.send(content=content, files=files)
            posted += len(batch)
        except discord.HTTPException as e:
            logger.warning("Failed to post screenshots batch: %s", e)

    # Cleanup resized temp files
    for p in prepared:
        if p.name.startswith("_discord_"):
            p.unlink(missing_ok=True)

    if posted:
        logger.info("Posted %d screenshot(s) to Discord thread", posted)

    return posted


def collect_run_screenshots(
    changes: list[dict[str, Any]],
    project_path: Path | str = ".",
) -> list[Path]:
    """Gather all smoke + E2E screenshot paths from a completed run's state changes.

    Reads smoke_screenshot_dir and e2e_screenshot_dir from each change dict.
    Returns deduplicated list of .png paths.
    """
    project = Path(project_path)
    seen_dirs: set[str] = set()
    all_paths: list[Path] = []

    for c in changes:
        for dir_key in ("smoke_screenshot_dir", "e2e_screenshot_dir"):
            rel_dir = c.get(dir_key, "")
            if not rel_dir or rel_dir in seen_dirs:
                continue
            seen_dirs.add(rel_dir)
            abs_dir = project / rel_dir
            if abs_dir.is_dir():
                all_paths.extend(sorted(abs_dir.rglob("*.png")))

    return all_paths


def get_active_thread() -> Any | None:
    """Get the Discord thread for the currently active run.

    Bridges events.py _run_state to external callers (watcher).
    """
    from .events import _run_state
    from .threads import get_thread

    for run_id in _run_state:
        thread = get_thread(run_id)
        if thread:
            return thread
    return None
