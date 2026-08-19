"""What the start guard knows must be what the LIST shows — no second copy.

Reported 2026-08-19: a project visible on the screen, with a start control next
to its name, refused the start with *"is not a project this screen knows;
register it first"*. Measured on the live server before the fix: **49 projects
served, 39 roots accepted, 10 refused** — 9 supplied only by the messaging
registry and 1 by a live process whose root the guard's own enumeration missed.

The cause is not the guard being wrong about any one project. It is that the
guard ENUMERATED ITS OWN SOURCES — a second definition of *what this screen
knows* — which was correct while the list had the same two, and went wrong
silently the moment a third arrived. `api/fleet.py` already carries a note about
exactly this happening to the union's downstream filter; that one was fixed and
this one was not, which is the same class twice: **completing a set means
auditing everything downstream of it**, because any later step that re-states
the set is a copy, and it drifted when the set changed.

So these tests assert the PROPERTY, not the instance. A fourth source added
tomorrow cannot reintroduce the bug without failing here, and no test needs
editing to cover it — which a list of source names could not promise.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modules" / "web"))

from set_orch.api import fleet as fleet_api  # noqa: E402
from set_orch.fleet.discovery import discover_projects  # noqa: E402


@pytest.fixture()
def three_sources(monkeypatch, tmp_path):
    """One project per source, and one that only ONE source names.

    The messaging-only entry is the reported case. It is here rather than in a
    parametrised list because it is the one the previous guard could not see,
    and a fixture that only exercised overlapping projects would pass on the
    broken version.
    """
    registered_root = tmp_path / "from-registry"
    messaging_root = tmp_path / "from-messaging"
    process_root = tmp_path / "from-process"
    for path in (registered_root, messaging_root, process_root):
        path.mkdir()

    class _Agent:
        pid = 4242
        project_root = str(process_root)
        project_name = "from-process"
        cwd = str(process_root)
        session_id = "s"
        kind = "interactive"

    monkeypatch.setattr(fleet_api, "_safe_registry",
                        lambda: [{"name": "from-registry", "path": str(registered_root)}])
    monkeypatch.setattr(fleet_api, "_safe_messaging",
                        lambda: [{"name": "from-messaging", "root": str(messaging_root)}])
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **kw: [_Agent()])
    return {
        "registry": str(registered_root),
        "messaging": str(messaging_root),
        "process": str(process_root),
    }


def test_every_source_that_can_put_a_project_on_the_screen_can_start_an_agent(three_sources):
    """The property, stated as a set comparison rather than as three assertions.

    Three named assertions would be a list, and a list is the thing that drifted.
    """
    known = fleet_api._known_roots()
    missing = {name: root for name, root in three_sources.items()
               if os.path.realpath(root) not in known}
    assert not missing, (
        "a project this screen shows cannot be started in: "
        + json.dumps(missing, indent=1)
        + " — the guard is enumerating its own sources again"
    )


def test_the_guard_and_the_list_are_the_same_set(three_sources):
    """The load-bearing one, and the reason it is not just three assertions.

    Whatever the union serves, the guard accepts; whatever the guard accepts,
    the union served. Stated in BOTH directions on purpose: a guard that widened
    to "any directory" would satisfy the first half while removing the
    protection the guard exists for.
    """
    del three_sources
    served = {
        os.path.realpath(p.root)
        for p in discover_projects(
            fleet_api.discover_agents(include_oneshot=True),
            registered=fleet_api._safe_registry(),
            messaging=fleet_api._safe_messaging(),
        )
        if p.root
    }
    assert fleet_api._known_roots() == served


def test_a_directory_no_source_names_is_still_refused(three_sources, tmp_path):
    """The protection is unchanged. Not choosing here chooses the permissive
    option: an endpoint that takes any existing directory starts an agent
    anywhere on the machine, and nothing on the screen ever offers that.
    """
    del three_sources
    stranger = tmp_path / "nobody-named-this"
    stranger.mkdir()
    assert os.path.realpath(str(stranger)) not in fleet_api._known_roots()


def test_an_archived_project_follows_the_list_rather_than_a_docstring(monkeypatch, tmp_path):
    """⚠ This test was first written the OTHER way round, and it was wrong.

    `discover_projects`'s docstring says an archived project *"is excluded by
    every other surface in this framework, so it is excluded here too"*. The code
    under it carries the flag and never filters on it. Measured 2026-08-19 on the
    live server: **19 of 49 served projects are archived**, and the screen shows
    them all.

    So filtering here — on the strength of that sentence — would have rebuilt the
    exact divergence this file exists to prevent, only mirrored: a project on
    screen, with a start control next to it, that the guard refuses. The rule is
    *what the screen shows*; the guard does not get an opinion about what ought
    to be shown.

    Kept as a test rather than a comment because a comment asks to be believed.
    """
    archived = tmp_path / "archived"
    archived.mkdir()
    monkeypatch.setattr(fleet_api, "_safe_registry",
                        lambda: [{"name": "archived", "path": str(archived), "archived": True}])
    monkeypatch.setattr(fleet_api, "_safe_messaging", lambda: [])
    monkeypatch.setattr(fleet_api, "discover_agents", lambda **kw: [])

    served = [p for p in discover_projects([], registered=fleet_api._safe_registry(),
                                           messaging=[]) if p.root]
    assert [p.archived for p in served] == [True], "the fixture did not produce an archived entry"
    assert os.path.realpath(str(archived)) in fleet_api._known_roots(), (
        "the guard filtered on `archived` while the list does not — the same "
        "divergence again, mirrored"
    )
