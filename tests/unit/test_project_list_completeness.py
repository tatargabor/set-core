"""`set-project list` must print every registered project.

Measured 2026-08-20: the registry held 43 projects and the command printed ONE.
A registered path that exists but is not a git checkout — an E2E run directory,
a scaffold, a stale entry — made `git worktree list` exit 128, and under
`set -e` that aborted the loop doing the printing.

The failure direction is why this has a test rather than a fix alone: the
command still exited through a pipeline that reported success, the header still
said "Registered projects:", and a short list is indistinguishable from a small
registry. Nothing anywhere said "truncated".
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SET_PROJECT = Path(__file__).resolve().parents[2] / "bin" / "set-project"

ROW = re.compile(r"^\s+\*?\s*(\S+)\s+->\s+")


@pytest.fixture
def registry(tmp_path):
    """A registry whose SECOND entry (in sorted order) is not a git checkout.

    Sorted order matters: the bug truncated at the first failing entry, so a
    fixture that puts the hazard last would pass against the broken code.
    """
    cfg = tmp_path / ".config" / "set-core"
    cfg.mkdir(parents=True)

    a_repo = tmp_path / "a-real-repo"
    a_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=a_repo, check=True)

    not_a_repo = tmp_path / "b-plain-directory"
    not_a_repo.mkdir()

    z_repo = tmp_path / "z-after-the-hazard"
    z_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=z_repo, check=True)

    (cfg / "projects.json").write_text(json.dumps({
        "default": None,
        "projects": {
            "a-real-repo": {"path": str(a_repo)},
            "b-plain-directory": {"path": str(not_a_repo)},
            "z-after-the-hazard": {"path": str(z_repo)},
        },
    }))
    return tmp_path


def _list(home):
    return subprocess.run(["bash", str(SET_PROJECT), "list"],
                          capture_output=True, text=True,
                          env=dict(os.environ, HOME=str(home)))


class TestEveryRegisteredProjectIsPrinted:
    def test_a_non_repository_does_not_truncate_the_list(self, registry):
        r = _list(registry)
        printed = {m.group(1) for m in (ROW.match(l) for l in r.stdout.splitlines()) if m}
        assert printed == {"a-real-repo", "b-plain-directory", "z-after-the-hazard"}, (
            f"truncated at a non-repository — printed {sorted(printed)}\n{r.stdout}"
        )

    def test_the_entry_AFTER_the_hazard_is_the_one_that_proves_it(self, registry):
        # Stated separately because it is the whole point: the bug dropped
        # everything downstream of the failure, so only a name sorting AFTER
        # the bad entry can distinguish "fixed" from "happened to work".
        r = _list(registry)
        assert "z-after-the-hazard" in r.stdout, r.stdout
