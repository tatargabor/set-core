"""Handing a path to the desktop — what it refuses, and what it starts.

The guard here answers one question: may this path be OPENED, or would the
desktop RUN it? So every test is about that difference, and two of them exist
because the plausible implementation gets them wrong in opposite directions:

- **a directory must still open.** Every traversable directory carries execute
  bits, so a uniform "no executables" check refuses all of them — and passes any
  suite written only against files.
- **a symlink must be judged by its target.** A link named `report.txt` pointing
  at a binary is exactly how an allowed-looking name reaches a program.

Nothing here mocks the filesystem: the paths are real files in `tmp_path` with
real modes, because a guard tested against a mock is tested against the
assumptions of whoever wrote the mock. `subprocess.Popen` IS patched — the one
thing that must not happen for real is a program starting.
"""

import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient
from set_orch.server import create_app
from set_orch.api import desktop as desktop_module


@pytest.fixture
def spawned(monkeypatch):
    """Every `Popen` the endpoint would make, captured instead of run."""
    calls = []

    class FakeProc:
        pid = 4242

    def fake_popen(argv, **kwargs):
        calls.append({"argv": list(argv), "kwargs": kwargs})
        return FakeProc()

    monkeypatch.setattr(desktop_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(desktop_module.shutil, "which", lambda name: "/usr/bin/" + name)
    return calls


@pytest.fixture
def client():
    return TestClient(create_app())


def post(client, path):
    return client.post("/api/desktop/open", json={"path": path})


# ─── What may be handed over ────────────────────────────────────────────────


def test_existing_file_is_handed_to_the_opener(client, spawned, tmp_path):
    doc = tmp_path / "shot.jpg"
    doc.write_bytes(b"not really a jpeg")

    res = post(client, str(doc))

    assert res.status_code == 200
    assert res.json()["opened"] is True
    assert len(spawned) == 1
    assert spawned[0]["argv"] == ["/usr/bin/xdg-open", str(doc)]


def test_directory_is_handed_over_despite_its_execute_bits(client, spawned, tmp_path):
    """The trap: a directory MUST have `x` set to be traversable.

    An executable-bit rule applied uniformly refuses every directory while
    looking entirely correct, so this asserts the one case that distinguishes
    the two implementations.
    """
    folder = tmp_path / "outputs"
    folder.mkdir()
    assert os.access(folder, os.X_OK), "fixture is not a traversable directory"

    res = post(client, str(folder))

    assert res.status_code == 200
    assert len(spawned) == 1


def test_the_success_answer_claims_only_the_hand_over(client, spawned, tmp_path):
    doc = tmp_path / "note.txt"
    doc.write_text("hello")

    body = post(client, str(doc)).json()

    # It may not claim a window appeared — the handler is detached and this
    # process cannot know. The wording is the whole point of the assertion.
    assert body["message"] == "handed to the desktop"


def test_the_hand_over_is_detached_and_silent(client, spawned, tmp_path):
    doc = tmp_path / "note.txt"
    doc.write_text("hello")

    post(client, str(doc))

    kwargs = spawned[0]["kwargs"]
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == desktop_module.subprocess.DEVNULL
    assert kwargs["stdout"] == desktop_module.subprocess.DEVNULL
    assert kwargs["stderr"] == desktop_module.subprocess.DEVNULL


def test_nothing_of_the_file_is_read(client, spawned, tmp_path):
    """The endpoint names a file; it never opens one.

    Measured by mtime/atime staying put is unreliable across filesystems, so the
    check is the direct one: the answer carries the path and nothing derived
    from the content — no size, no type, no excerpt.
    """
    doc = tmp_path / "secret.txt"
    doc.write_text("partner name and an order number")

    body = post(client, str(doc)).json()

    assert set(body) == {"opened", "path", "message"}
    assert "secret" not in body["message"]
    assert body["path"] == str(doc)


# ─── What must never be handed over ─────────────────────────────────────────


def test_missing_path_is_refused(client, spawned, tmp_path):
    res = post(client, str(tmp_path / "nope.png"))

    assert res.status_code == 400
    assert "no such file" in res.json()["detail"]
    assert spawned == []


def test_relative_path_is_refused(client, spawned):
    res = post(client, "relative/thing.txt")

    assert res.status_code == 400
    assert "absolute" in res.json()["detail"]
    assert spawned == []


def test_executable_file_is_refused(client, spawned, tmp_path):
    script = tmp_path / "deploy.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)

    res = post(client, str(script))

    assert res.status_code == 400
    assert "executable" in res.json()["detail"]
    assert spawned == []


def test_symlink_to_an_executable_is_refused(client, spawned, tmp_path):
    """Judged by the target — though `os.access` would follow the link anyway.

    Kept as a behaviour check, NOT as the proof that resolution happens: with
    `realpath` removed this test still passes, measured 2026-08-26. The test that
    actually distinguishes the two implementations is the next one, because a
    SUFFIX is read off the string and no syscall resolves it for you.
    """
    real = tmp_path / "payload.bin"
    real.write_text("#!/bin/sh\necho hi\n")
    real.chmod(real.stat().st_mode | stat.S_IXUSR)
    link = tmp_path / "report.txt"
    link.symlink_to(real)

    res = post(client, str(link))

    assert res.status_code == 400
    assert "executable" in res.json()["detail"]
    assert spawned == []


def test_symlink_named_like_a_document_but_pointing_at_a_launcher_is_refused(
    client, spawned, tmp_path
):
    """The case that proves the guard resolves before it judges.

    `os.access` follows a link on its own, so the executable rule survives a
    missing `realpath`. The suffix rule does not: `notes.txt` ends in `.txt`
    whatever it points at, so a guard reading the REQUEST STRING hands a desktop
    entry to the opener and starts its `Exec=` line.
    """
    entry = tmp_path / "launcher.desktop"
    entry.write_text("[Desktop Entry]\nExec=/bin/sh -c 'touch /tmp/pwned'\n")
    entry.chmod(0o644)
    link = tmp_path / "notes.txt"
    link.symlink_to(entry)

    res = post(client, str(link))

    assert res.status_code == 400
    assert "launcher" in res.json()["detail"]
    assert spawned == []


def test_desktop_entry_is_refused_even_without_the_executable_bit(client, spawned, tmp_path):
    entry = tmp_path / "launcher.desktop"
    entry.write_text("[Desktop Entry]\nExec=/bin/sh -c 'touch /tmp/pwned'\n")
    entry.chmod(0o644)
    assert not os.access(entry, os.X_OK), "fixture must not be executable"

    res = post(client, str(entry))

    assert res.status_code == 400
    assert "launcher" in res.json()["detail"]
    assert spawned == []


# ─── A refusal is an answer ─────────────────────────────────────────────────


def test_missing_opener_is_a_refusal_naming_it(client, monkeypatch, tmp_path):
    doc = tmp_path / "note.txt"
    doc.write_text("hello")
    started = []
    monkeypatch.setattr(desktop_module.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        desktop_module.subprocess, "Popen", lambda *a, **k: started.append(a)
    )

    res = post(client, str(doc))

    assert res.status_code == 501
    assert "xdg-open" in res.json()["detail"]
    assert started == []


def test_the_guard_is_callable_without_a_web_server(tmp_path):
    """`refusal()` is the unit the route delegates to, and it says WHY.

    A boolean guard would make the endpoint answer "no" without a reason, and a
    reason the reader cannot see is the same as a link that silently does
    nothing — the defect this whole change is about.
    """
    doc = tmp_path / "ok.txt"
    doc.write_text("x")

    assert desktop_module.refusal(str(doc)) is None
    assert desktop_module.refusal("") == "path must be absolute"
    assert desktop_module.refusal("rel/x") == "path must be absolute"


# ─── B-89: the association, not the permission bit ───────────────────────────


def test_a_644_archive_a_runtime_executes_is_refused(client, spawned, tmp_path):
    """The measurement that found B-89, held as a test.

    Measured 2026-08-27 on a running desktop: a `.jar` with mode 644 and no
    executable bit anywhere passed this guard, and its handler was
    `openjdk-7-java.desktop` — which runs it. Data by permission, a program by
    association.
    """
    for name in ("harmless.jar", "installer.appimage", "setup.run",
                 "launch.jnlp", "pack.msi", "app.deb", "sheet.xlsm"):
        target = tmp_path / name
        target.write_text("not really, but the handler does not read it either\n")
        assert target.stat().st_mode & 0o111 == 0, "the point is that it is NOT executable"

        res = post(client, str(target))

        assert res.status_code == 400, name
        detail = res.json()["detail"]
        assert "RUN by whatever the desktop associates" in detail, f"{name}: {detail}"
        # And the reason must NOT be the permission bit — a reader sent to
        # inspect permissions that are not the cause looks at the wrong thing
        # and concludes the guard is broken.
        assert "executable bit" not in detail, f"{name}: {detail}"

    # And the ORDER: a `.jar` that also carries the bit must still name the
    # association, because that is the stronger fact and the one a reader can
    # act on. Reporting the bit would send them to `chmod`, which fixes nothing.
    both = tmp_path / "signed.jar"
    both.write_text("x")
    both.chmod(both.stat().st_mode | stat.S_IXUSR)
    detail = post(client, str(both)).json()["detail"]
    assert "RUN by whatever the desktop associates" in detail, detail
    assert "executable bit" not in detail, detail
    assert spawned == []


def test_a_local_page_that_can_read_this_machine_is_refused(client, spawned, tmp_path):
    """`.html` is the milder severity and the same class.

    Nothing is executed — but the page opens at a `file://` origin that can read
    local files, and the text that named it was written by whatever an agent ran.
    """
    for name in ("report.html", "index.htm", "page.xhtml"):
        target = tmp_path / name
        target.write_text("<p>hello</p>\n")

        res = post(client, str(target))

        assert res.status_code == 400, name
        assert "local page" in res.json()["detail"], name
    assert spawned == []


def test_an_ordinary_file_is_still_handed_over(client, spawned, tmp_path):
    """The widening must refuse NOTHING that was already working.

    A guard that grows is only safe if the growth is measured in both
    directions. These are the four kinds an agent actually prints the path of.
    """
    for name in ("shot.png", "clip.mp4", "report.pdf", "notes.docx", "plan.md",
                 "diagram.svg", "script.py"):
        target = tmp_path / name
        target.write_text("x")

        res = post(client, str(target))

        assert res.status_code == 200, f"{name}: {res.json()}"
    assert len(spawned) == 7


def test_the_guard_asks_the_local_desktop_NOTHING(monkeypatch, tmp_path):
    """Same input, same verdict, on every machine — asserted rather than assumed.

    A guard that queried `xdg-mime` or looked for a handler would give a
    different answer on every machine and per user, and could not be tested at
    all. So the refusals are read off the PATH, and this test removes the two
    ways this module could reach a subprocess and checks that every verdict is
    unchanged.
    """
    import subprocess as real_subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("refusal() consulted something outside the path")

    monkeypatch.setattr(desktop_module.subprocess, "run", forbidden)
    monkeypatch.setattr(desktop_module.subprocess, "Popen", forbidden)
    monkeypatch.setattr(desktop_module.shutil, "which", forbidden)
    assert real_subprocess is not None  # the import above is the thing being blocked

    jar = tmp_path / "harmless.jar"
    jar.write_text("x")
    doc = tmp_path / "notes.txt"
    doc.write_text("x")

    assert "RUN by whatever the desktop associates" in (desktop_module.refusal(str(jar)) or "")
    assert desktop_module.refusal(str(doc)) is None
