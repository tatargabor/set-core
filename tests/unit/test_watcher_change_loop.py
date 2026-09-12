"""The watcher's per-change loop must not resolve the project per changed path — B-146.

A batch of N changed paths used to construct `LineagePaths` — and through it
`SetRuntime`, and through that two `git rev-parse` subprocesses — N times, on the
event loop. Measured 2026-09-12 on the live dashboard: a 12 639-path batch (a
Next.js build output inside a watched project root) froze the event loop for
177 s; every HTTP request timed out while the process looked alive.

Driven rather than asserted about: a fake `watchfiles` yields ONE batch of many
unrelated paths and the test counts project-name resolutions during the batch.
The bound is "at most once per watch", not "zero" — the basename genuinely has to
be resolved, just not per path.
"""

from __future__ import annotations

import asyncio
import sys
import types

from set_orch import paths as paths_mod
from set_orch.watcher import ProjectWatcher


def _fake_watchfiles(monkeypatch, batches):
    mod = types.ModuleType("watchfiles")

    class Change:  # the three values watchfiles.Change carries
        added = 1
        modified = 2
        deleted = 3

    async def awatch(*_dirs, **_kw):
        for batch in batches:
            yield batch

    mod.Change = Change
    mod.awatch = awatch
    monkeypatch.setitem(sys.modules, "watchfiles", mod)
    return mod


def test_a_batch_of_many_paths_resolves_the_project_at_most_once(tmp_path, monkeypatch):
    monkeypatch.setattr(paths_mod, "SET_TOOLS_DATA_DIR", str(tmp_path / "data"))
    resolutions: list[str | None] = []

    def counting(project_path=None):
        resolutions.append(project_path)
        return "watched-project"

    monkeypatch.setattr(paths_mod, "resolve_project_name", counting)

    watcher = ProjectWatcher("watched-project", tmp_path)
    n = 500
    fake = _fake_watchfiles(
        monkeypatch,
        [{(fake_change, str(tmp_path / ".next" / f"chunk-{i}.js"))
          for i, fake_change in zip(range(n), [2] * n)}],
    )
    assert fake.Change.modified == 2
    resolutions.clear()  # the constructor's own resolutions are not the subject

    seen: list[tuple] = []

    async def callback(*args):
        seen.append(args)

    asyncio.run(watcher.watch(callback))

    assert seen == [], "unrelated paths must not fire the callback"
    assert len(resolutions) <= 1, (
        f"{len(resolutions)} project resolutions for one batch of {n} paths — "
        "each one is two git subprocesses on the event loop"
    )
