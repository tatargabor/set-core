"""The file endpoints — and above all the guard on the write path.

This repository's whole 2026-07-19 safety track exists because write paths into a
project tree were unguarded. `api/files.py` adds one deliberately, at a person's
request, so the guard is the part that gets the most tests here — and one of them
exists to prove the guard is a guard rather than a comment (see the module note on
`test_a_symlink_out_of_the_project_is_refused`).

Everything runs against a real temporary tree with real symlinks. A guard tested
against a mocked filesystem is a guard tested against the assumptions of whoever
wrote the mock, which is the one place the bug will not be.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient
from set_orch.server import create_app
from set_orch.api import files as files_module


@pytest.fixture
def project(tmp_path):
    """A project tree, and a second directory OUTSIDE it to escape to."""
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.ts").write_text("const a = 1\nconst b = 2\n")
    (root / "README.md").write_text("# hello\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("PRIVATE-VALUE-DO-NOT-SERVE\n")
    return root, outside


@pytest.fixture
def client(monkeypatch, project):
    """A client for which exactly one root is known to the screen.

    `_known_roots` is patched rather than the registry, because that is the
    function the endpoint actually asks — patching the registry would test a
    different resolution path than the one that ships.
    """
    root, _ = project
    monkeypatch.setattr(files_module, "_known_roots", lambda: {os.path.realpath(root)})
    return TestClient(create_app(web_dist_dir=None))


# ─── The guard ───────────────────────────────────────────────────────────────


def test_a_root_the_screen_does_not_know_is_refused(client, project):
    _, outside = project
    r = client.get("/api/fleet/files", params={"root": str(outside)})
    assert r.status_code == 400
    assert "not a project this screen knows" in r.json()["detail"]


def test_a_traversal_out_of_the_project_is_refused(client, project):
    root, _ = project
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "../outside/secret.txt"})
    assert r.status_code == 403
    assert "PRIVATE-VALUE" not in r.text


def test_a_symlink_out_of_the_project_is_refused(client, project):
    """The case a `..`-scanning guard passes straight through.

    The request string contains no `..` and names a path inside the project. Only
    resolving it reveals that the file is somewhere else entirely — which is why
    `_confine` compares AFTER `resolve()`, and why mutating it to compare before
    turns this test red (measured; the other guard tests stay green, so this one
    is the one carrying the finding).
    """
    root, outside = project
    (root / "escape.txt").symlink_to(outside / "secret.txt")
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "escape.txt"})
    assert r.status_code == 403
    assert "PRIVATE-VALUE" not in r.text


def test_a_symlinked_PARENT_directory_is_refused(client, project):
    """The same escape one level up — the link is a directory, not the file."""
    root, outside = project
    (root / "elsewhere").symlink_to(outside, target_is_directory=True)
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "elsewhere/secret.txt"})
    assert r.status_code == 403
    assert "PRIVATE-VALUE" not in r.text


def test_an_absolute_path_is_refused(client, project):
    root, outside = project
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": str(outside / "secret.txt")})
    assert r.status_code == 403


def test_the_refusal_does_not_say_whether_the_file_exists(client, project):
    """A probe must learn nothing from the difference between two refusals.

    Same status, same body, for a path outside the root that exists and one that
    does not. Anything else turns this endpoint into a polite way of asking what
    is on the machine.
    """
    root, outside = project
    real = client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": "../outside/secret.txt"})
    fake = client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": "../outside/nothing-here.txt"})
    assert real.status_code == fake.status_code == 403
    assert real.json() == fake.json()


# ─── Listing ─────────────────────────────────────────────────────────────────


def test_a_listing_says_which_producer_ran(client, project):
    """A tree that is not a repository is answered by the walk, and says so.

    "no files" from a non-repository and "no files" from an empty repository are
    different facts; a caller that cannot tell them apart debugs the wrong one.
    """
    root, _ = project
    r = client.get("/api/fleet/files", params={"root": str(root)})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "walk"
    assert "README.md" in body["files"]
    assert "src/app.ts" in body["files"]


def test_a_truncated_listing_says_so(client, project, monkeypatch):
    """The cap, the true count and the flag travel together.

    A list cut to its cap and served as a plain array reads as the whole project:
    the reader concludes a file is not there when the answer merely stopped.
    """
    root, _ = project
    monkeypatch.setattr(files_module, "MAX_FILES", 1)
    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    assert body["truncated"] is True
    assert body["cap"] == 1
    assert body["total"] >= 2
    assert len(body["files"]) == 1


def test_a_git_project_is_listed_by_git(client, project):
    """Ignored files stay out, uncommitted files come in.

    Both halves matter and only together: the first is why git is used at all,
    the second is why `--others` is on the command — the file an agent wrote a
    minute ago is exactly the one a reader wants to open, and it is not committed.
    """
    import subprocess
    root, _ = project
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text("ignored/\n")
    (root / "ignored").mkdir()
    (root / "ignored" / "build.js").write_text("x\n")
    (root / "fresh.ts").write_text("just written by an agent\n")

    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    assert body["source"] == "git"
    assert "ignored/build.js" not in body["files"]
    assert "fresh.ts" in body["files"]


# ─── Reading ─────────────────────────────────────────────────────────────────


def test_a_text_file_comes_back_with_its_identity(client, project):
    root, _ = project
    body = client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": "src/app.ts"}).json()
    assert body["content"] == "const a = 1\nconst b = 2\n"
    assert len(body["identity"]) == 64


def test_a_file_over_the_cap_is_refused_with_its_size(client, project, monkeypatch):
    """A refusal naming the size, never a truncated prefix.

    A prefix is the dangerous answer: it looks exactly like a whole file, and on
    this screen it can be saved back over the real one.
    """
    root, _ = project
    monkeypatch.setattr(files_module, "MAX_BYTES", 4)
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "src/app.ts"})
    assert r.status_code == 413
    assert "24" in r.json()["detail"] and "4" in r.json()["detail"]


def test_a_binary_file_is_refused_rather_than_mangled(client, project):
    root, _ = project
    (root / "logo.bin").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "logo.bin"})
    assert r.status_code == 415
    assert "text" in r.json()["detail"]


def test_an_empty_file_is_not_a_failure(client, project):
    root, _ = project
    (root / "empty.ts").write_text("")
    body = client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": "empty.ts"}).json()
    assert body["content"] == ""
    assert body["bytes"] == 0


def test_nothing_is_cached_between_reads(client, project):
    """The second read is a read, not a memory of the first."""
    root, _ = project
    first = client.get("/api/fleet/files/content",
                       params={"root": str(root), "path": "README.md"}).json()
    (root / "README.md").write_text("# changed by somebody else\n")
    second = client.get("/api/fleet/files/content",
                        params={"root": str(root), "path": "README.md"}).json()
    assert second["content"] == "# changed by somebody else\n"
    assert second["identity"] != first["identity"]


# ─── Writing ─────────────────────────────────────────────────────────────────


def _read(client, root, path):
    return client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": path}).json()


def test_a_write_lands_when_the_file_is_unchanged(client, project):
    root, _ = project
    before = _read(client, root, "src/app.ts")
    r = client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "src/app.ts",
        "content": "const a = 99\n", "identity": before["identity"],
    })
    assert r.status_code == 200
    assert (root / "src" / "app.ts").read_text() == "const a = 99\n"
    # The answer carries the identity of what was WRITTEN, so the next save is
    # checked against reality rather than against what the caller last read.
    assert r.json()["identity"] == _read(client, root, "src/app.ts")["identity"]


def test_a_stale_identity_is_refused_and_the_file_is_untouched(client, project):
    """The ordinary case on this screen: an agent edited the same file.

    Both halves are asserted, and the second is the one that matters — a 409 that
    wrote anyway would be worse than no check at all, because the status says it
    did not.
    """
    root, _ = project
    before = _read(client, root, "src/app.ts")
    (root / "src" / "app.ts").write_text("written by an agent\n")
    r = client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "src/app.ts",
        "content": "written by the reader\n", "identity": before["identity"],
    })
    assert r.status_code == 409
    assert "changed on disk" in r.json()["detail"]
    assert (root / "src" / "app.ts").read_text() == "written by an agent\n"


def test_a_write_does_not_recreate_a_deleted_file(client, project):
    """A deletion is somebody's act; writing the file back would undo it."""
    root, _ = project
    before = _read(client, root, "README.md")
    (root / "README.md").unlink()
    r = client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "README.md",
        "content": "resurrected\n", "identity": before["identity"],
    })
    assert r.status_code == 404
    assert not (root / "README.md").exists()


def test_a_write_leaves_no_temporary_file_behind(client, project):
    """Atomic means a replace, and a replace leaves nothing to clean up."""
    root, _ = project
    before = _read(client, root, "README.md")
    client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "README.md",
        "content": "# done\n", "identity": before["identity"],
    })
    assert [p.name for p in root.iterdir() if p.name.startswith(".set-file-")] == []


def test_a_write_outside_a_known_root_is_refused(client, project):
    """The guard is on the write path too, not only on the read path."""
    root, outside = project
    r = client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "../outside/secret.txt",
        "content": "overwritten\n", "identity": "whatever",
    })
    assert r.status_code == 403
    assert (outside / "secret.txt").read_text() == "PRIVATE-VALUE-DO-NOT-SERVE\n"


# ─── Confidentiality ─────────────────────────────────────────────────────────


def test_no_log_record_carries_file_content(client, project, caplog):
    """The framework may display a consumer's source; it may not record it.

    Exercised over the whole surface — a successful write, a refused write, a
    binary refusal — because a single happy-path check would say nothing about
    the error paths, and error paths are where a helpful `%s` of the record gets
    added.
    """
    root, _ = project
    secret = "PARTNER-NAME-AND-INVOICE-2026-07"
    (root / "src" / "app.ts").write_text(secret + "\n")
    caplog.set_level("DEBUG")

    before = _read(client, root, "src/app.ts")
    client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "src/app.ts",
        "content": secret + " edited\n", "identity": before["identity"],
    })
    client.put("/api/fleet/files/content", json={
        "root": str(root), "path": "src/app.ts",
        "content": secret + " again\n", "identity": "stale",
    })
    (root / "bin.dat").write_bytes(b"\xff\xfe" + secret.encode())
    client.get("/api/fleet/files/content", params={"root": str(root), "path": "bin.dat"})

    assert caplog.records, "nothing was logged at all — the check would be vacuous"
    for record in caplog.records:
        assert secret not in record.getMessage()
