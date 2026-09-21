"""A project watcher must not take a slot from the request thread pool.

`watchfiles.awatch` runs its blocking loop through `anyio.to_thread.run_sync`
on the default limiter and holds that slot for as long as it watches. With
more registered projects than the limiter's 40 tokens, every sync endpoint
and every static file waited seconds for a slot (measured 2026-09-21: 48
projects, 40 threads parked in nanosleep, ~2-4 s on `index.html`).
"""

import asyncio
import sys
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.watcher import WatcherManager  # noqa: E402


def test_each_watcher_adds_its_own_thread_slot(tmp_path):
    async def scenario():
        limiter = anyio.to_thread.current_default_thread_limiter()
        before = limiter.total_tokens
        manager = WatcherManager()
        for i in range(3):
            project = tmp_path / f"p{i}"
            project.mkdir()
            manager._start_project_watcher(f"p{i}", project)
        grown = limiter.total_tokens - before
        await manager.stop()
        return grown

    assert asyncio.run(scenario()) == 3
