"""A project watcher must not register an inotify watch on every directory of the tree.

The watcher matches only the state file and `orchestration.log` by name, directly
inside their directories, but it used to watch the project root recursively.
Measured 2026-09-24 on the dashboard server: 48 projects, 123 637 inotify watches,
the largest instance 36 302 watches against a 36 838-directory project, and a
consumer's build output streaming every write through the event loop until the
fleet screen stopped taking keystrokes.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch import watcher as watcher_mod  # noqa: E402
from set_orch.watcher import ProjectWatcher  # noqa: E402

linux_only = pytest.mark.skipif(
    not Path("/proc/self/fdinfo").is_dir(), reason="counts inotify watches via /proc"
)


def _inotify_watches() -> int:
    total = 0
    for fd in os.listdir("/proc/self/fdinfo"):
        try:
            with open(f"/proc/self/fdinfo/{fd}") as f:
                total += sum(1 for line in f if line.startswith("inotify wd:"))
        except OSError:
            pass
    return total


async def _noop(*_args):
    pass


@linux_only
def test_deep_project_tree_is_not_watched(tmp_path):
    project = tmp_path / "proj"
    deep = project
    for i in range(40):
        deep = deep / f"d{i}"
    deep.mkdir(parents=True)
    (project / "set" / "orchestration").mkdir(parents=True)

    async def scenario():
        before = _inotify_watches()
        w = ProjectWatcher("proj", project)
        task = asyncio.create_task(w.watch(_noop))
        await asyncio.sleep(1.0)
        during = _inotify_watches()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return during - before

    added = asyncio.run(scenario())
    # At most one watch per candidate dir (root, project-local orchestration dir,
    # the state dir, the log dir); the 40 nested dirs must not add one each.
    assert 1 <= added <= 4, added


def test_log_dir_created_after_start_is_picked_up(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher_mod, "DIR_RECHECK_MS", 200)
    project = tmp_path / "proj"
    project.mkdir()
    events = []

    async def callback(name, event_type, data):
        events.append(event_type)

    async def scenario():
        w = ProjectWatcher("proj", project)
        task = asyncio.create_task(w.watch(callback))
        await asyncio.sleep(0.5)
        log_dir = project / "set" / "orchestration"
        log_dir.mkdir(parents=True)
        await asyncio.sleep(1.0)  # past a recheck, so the new dir is watched
        (log_dir / "orchestration.log").write_text("first line\n")
        for _ in range(50):
            if "log_lines" in events:
                break
            await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
    assert "log_lines" in events
