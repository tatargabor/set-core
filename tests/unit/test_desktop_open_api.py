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
