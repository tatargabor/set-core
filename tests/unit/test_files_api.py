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
from set_orch.api import fleet as fleet_module


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
    function the resolution actually asks — patching the registry would test a
    different path than the one that ships.

    Patched on `fleet`, not on `files`: the endpoint asks
    `_start_location_verdict`, which reads `_known_roots` in ITS own module. A
    patch on `files` was silently ineffective the moment the guard started
    delegating — measured here, as nineteen tests going red at once.
    """
    root, _ = project
    monkeypatch.setattr(fleet_module, "_known_roots", lambda: {os.path.realpath(root)})
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
    detail = r.json()["detail"]
    assert detail["reason"] == "too-large"
    assert detail["bytes"] == 24 and detail["cap"] == 4
    # And the SENTENCE is still there for any reader that is not this panel.
    assert "24" in detail["message"] and "4" in detail["message"]


def test_a_binary_with_no_view_names_its_TYPE_and_size(client, project):
    """The refusal that replaced *"not a text file"*.

    A caller told only that cannot say what the file IS — it cannot draw it, and
    it cannot tell a PDF from a corrupt file. Both of those are things a reader
    standing in front of the panel wants to know, and neither is derivable from
    the absence of text.
    """
    root, _ = project
    (root / "report.pdf").write_bytes(b"%PDF-1.4\n\x00\xff binary tail\n")
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "report.pdf"})
    assert r.status_code == 415
    detail = r.json()["detail"]
    assert detail["reason"] == "no-view"
    assert detail["media_type"] == "application/pdf"
    assert detail["bytes"] > 0
    assert "application/pdf" in detail["message"]


def test_the_two_refusals_stay_distinguishable(client, project, monkeypatch):
    """*Too large* and *no view for this type* send the reader to two places.

    A panel that collapsed them into one sentence would send half its readers to
    the wrong one — and in particular a large IMAGE is refused for its size, not
    for its type, and saying otherwise reports a limit the framework does not
    have.
    """
    root, _ = project
    (root / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    monkeypatch.setattr(files_module, "MAX_RAW_BYTES", 8)

    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "shot.png"})
    assert r.status_code == 413
    detail = r.json()["detail"]
    assert detail["reason"] == "too-large"
    assert detail["media_type"] == "image/png", "the type is still named — it is not the cause"
    assert detail["cap"] == 8


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


# ─── A worktree of a known project ───────────────────────────────────────────


@pytest.fixture
def repo_with_worktree(tmp_path):
    """A real git repository with a real second working tree.

    Real git rather than a patched verdict, because what is being tested IS the
    reuse: the endpoint now asks the same function the start path asks, and a
    stubbed answer would prove only that the stub was called.
    """
    import subprocess

    main = tmp_path / "proj"
    (main / "src").mkdir(parents=True)
    (main / "src" / "app.ts").write_text("main branch\n")

    def git(*args, cwd=main):
        subprocess.run(["git", *args], cwd=str(cwd), check=True,
                       capture_output=True, env={**os.environ,
                                                 "GIT_AUTHOR_NAME": "t",
                                                 "GIT_AUTHOR_EMAIL": "t@e",
                                                 "GIT_COMMITTER_NAME": "t",
                                                 "GIT_COMMITTER_EMAIL": "t@e",
                                                 "HOME": str(tmp_path)})

    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-qm", "one")
    wt = tmp_path / "proj-wt-mobil"
    git("worktree", "add", "-q", "-b", "change/mobil", str(wt))
    # The file the agent in the worktree is actually looking at, and which the
    # main checkout does NOT have. This is the reported case.
    (wt / "openspec").mkdir()
    (wt / "openspec" / "plan.md").write_text("only in the worktree\n")
    (wt / "src" / "app.ts").write_text("worktree branch\n")
    return main, wt


@pytest.fixture
def wt_client(monkeypatch, repo_with_worktree):
    main, _ = repo_with_worktree
    monkeypatch.setattr(fleet_module, "_known_roots", lambda: {os.path.realpath(main)})
    return TestClient(create_app(web_dist_dir=None))


def test_a_worktree_of_a_known_project_can_be_listed(wt_client, repo_with_worktree):
    _, wt = repo_with_worktree
    r = wt_client.get("/api/fleet/files", params={"root": str(wt)})
    assert r.status_code == 200
    assert "openspec/plan.md" in r.json()["files"]


def test_a_worktree_file_is_read_from_the_worktree_not_from_main(wt_client, repo_with_worktree):
    """The silent half of the defect: same path, two checkouts, one right answer."""
    main, wt = repo_with_worktree
    from_wt = wt_client.get("/api/fleet/files/content",
                            params={"root": str(wt), "path": "src/app.ts"})
    from_main = wt_client.get("/api/fleet/files/content",
                              params={"root": str(main), "path": "src/app.ts"})
    assert from_wt.status_code == 200 and from_main.status_code == 200
    assert from_wt.json()["content"] == "worktree branch\n"
    assert from_main.json()["content"] == "main branch\n"


def test_a_save_goes_back_to_the_WORKTREE_it_came_from(wt_client, repo_with_worktree):
    """Reading from a worktree and writing back to main would be a silent seam.

    The read side is asserted above; this is the other half, and the two hide
    each other if only one is checked — a write that landed in main would still
    return 200, and the next read of the worktree would return the unchanged
    text, which reads as "the save did not take" rather than "the save went
    somewhere else". So the assertion is on BOTH checkouts: the worktree has the
    new text and main still has its own.
    """
    main, wt = repo_with_worktree
    before = _read(wt_client, wt, "src/app.ts")
    r = wt_client.put("/api/fleet/files/content", json={
        "root": str(wt), "path": "src/app.ts",
        "content": "edited in the worktree\n", "identity": before["identity"],
    })
    assert r.status_code == 200, r.text
    assert (wt / "src" / "app.ts").read_text() == "edited in the worktree\n"
    assert (main / "src" / "app.ts").read_text() == "main branch\n"


def test_a_worktree_read_obeys_the_SAME_cap(wt_client, repo_with_worktree, monkeypatch):
    """Widening which checkouts may be read must not widen what may be read out.

    The limits live on the shared route, so this asserts that the worktree took
    that route rather than one of its own.
    """
    _, wt = repo_with_worktree
    monkeypatch.setattr(files_module, "MAX_BYTES", 4)
    r = wt_client.get("/api/fleet/files/content",
                      params={"root": str(wt), "path": "openspec/plan.md"})
    assert r.status_code == 413
    assert r.json()["detail"]["reason"] == "too-large"


def test_an_unrelated_directory_is_still_refused(wt_client, tmp_path):
    """Widening to worktrees must not widen to anything else."""
    stranger = tmp_path / "stranger"
    stranger.mkdir()
    r = wt_client.get("/api/fleet/files", params={"root": str(stranger)})
    assert r.status_code == 400
    assert "nor a worktree of one" in r.json()["detail"]


def test_a_subdirectory_of_a_known_root_is_still_refused(wt_client, repo_with_worktree):
    """The case a prefix test would let in — `node_modules` as a project."""
    main, _ = repo_with_worktree
    r = wt_client.get("/api/fleet/files", params={"root": str(main / "src")})
    assert r.status_code == 400


def test_the_payload_checkouts_and_the_endpoints_agree(wt_client, repo_with_worktree, tmp_path):
    """What the screen SHIPS as readable and what the endpoints ACCEPT are one set.

    The fleet payload now tells the browser which checkouts exist, so that the
    terminal can route a path to the panel instead of to the desktop without
    asking the server about it. That list is a second statement of something the
    endpoints already decide — and this repository has paid, on a live report,
    for exactly two such statements drifting apart (`files.py:_known_root`).

    So the agreement is asserted in BOTH directions: everything the payload
    lists, the listing endpoint serves; and something it omits, the endpoint
    refuses. A test of only the first direction passes for a payload that lists
    the entire filesystem.
    """
    main, wt = repo_with_worktree
    known = {os.path.realpath(main)}
    listed = fleet_module._servable_checkouts(str(main), known)

    assert os.path.realpath(main) in listed
    assert os.path.realpath(wt) in listed, "the worktree the agent stands in must be listed"

    for checkout in listed:
        r = wt_client.get("/api/fleet/files", params={"root": checkout})
        assert r.status_code == 200, f"payload lists {checkout} but the endpoint refuses it"

    stranger = tmp_path / "stranger"
    stranger.mkdir()
    assert str(stranger) not in listed
    assert wt_client.get("/api/fleet/files", params={"root": str(stranger)}).status_code == 400


def test_a_project_the_screen_does_not_know_lists_no_checkouts(repo_with_worktree):
    """The empty answer is a real answer, and it is the one that fails safe.

    A root outside the known set has no servable checkout — not its own root and
    not its worktrees — so the browser is told about nothing it may not read.
    """
    main, _ = repo_with_worktree
    assert fleet_module._servable_checkouts(str(main), set()) == []


# ─── Path fidelity, the ignored flag, and status ─────────────────────────────


def _repo(root):
    """A real git repository at `root`, committed, with git's own quoting ON.

    `core.quotePath` is left at its default deliberately: the defect this file
    now covers only exists because that default is on, and a fixture that turned
    it off would produce a test that passes against the broken code.
    """
    import subprocess

    def git(*args):
        subprocess.run(["git", *args], cwd=str(root), check=True,
                       capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    git("add", "-A")
    git("commit", "-qm", "one")
    return git


def test_a_non_ascii_name_is_listed_as_it_is_on_disk(client, project):
    """The phantom-directory defect: git RENDERS a path, `-z` returns one.

    Measured 2026-08-26 on a consumer checkout — 11 of 1794 paths came back as
    `"docs/…\\303\\263….md"`. The tree builder read the leading quote as part of
    the first segment, so a directory named `"docs` appeared that nobody made,
    the real files sat unreachable beneath it, and the path sent back named no
    file. Both halves are asserted here: the name comes back intact, AND that
    same string opens the file.
    """
    root, _ = project
    name = "docs/Összéfoglaló.md"
    (root / "docs").mkdir()
    (root / name).write_text("tartalom\n")
    _repo(root)

    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    assert name in body["files"], body["files"]
    assert not any(f.startswith('"') for f in body["files"])

    content = client.get("/api/fleet/files/content",
                         params={"root": str(root), "path": name})
    assert content.status_code == 200
    assert content.json()["content"] == "tartalom\n"


def test_ignored_files_are_absent_until_they_are_asked_for(client, project):
    root, _ = project
    (root / ".gitignore").write_text(".set/\nnode_modules/\n")
    (root / ".set").mkdir()
    (root / ".set" / "state.json").write_text("{}\n")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "dep.js").write_text("x\n")
    _repo(root)

    off = client.get("/api/fleet/files", params={"root": str(root)}).json()
    assert ".set/state.json" not in off["files"]
    assert off["ignored"] is False

    on = client.get("/api/fleet/files",
                    params={"root": str(root), "ignored": "true"}).json()
    assert ".set/state.json" in on["files"]
    assert on["ignored"] is True
    # The bound is real and stated: lifting the ignore rules does NOT lift the
    # skip list. 36 149 paths against a cap of 20 000 was the measured
    # alternative — one silent absence traded for another.
    assert "node_modules/dep.js" not in on["files"]
    # And an entry that is only here because the flag was set says so.
    assert on["status"][".set/state.json"] == "!!"


def test_the_ignored_flag_does_not_lift_the_cap(client, project, monkeypatch):
    root, _ = project
    (root / ".gitignore").write_text(".set/\n")
    (root / ".set").mkdir()
    for i in range(5):
        (root / ".set" / f"f{i}.json").write_text("{}\n")
    _repo(root)
    monkeypatch.setattr(files_module, "MAX_FILES", 2)
    body = client.get("/api/fleet/files",
                      params={"root": str(root), "ignored": "true"}).json()
    assert body["truncated"] is True
    assert body["cap"] == 2
    assert len(body["files"]) == 2


def test_status_marks_modified_and_untracked_and_nothing_else(client, project):
    root, _ = project
    _repo(root)
    (root / "README.md").write_text("# hello, edited\n")
    (root / "fresh.ts").write_text("just written by an agent\n")

    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    status = body["status"]
    assert status["README.md"].strip() == "M"
    assert status["fresh.ts"] == "??"
    # A clean file is ABSENT from the map, not present with a blank code: absent
    # means clean, and one representation of clean is enough.
    assert "src/app.ts" not in status


def test_a_directory_that_is_not_a_repository_reports_no_status(client, project):
    """`null`, never `{}`.

    `{}` says *I asked, and everything is clean*. `null` says *there was nothing
    to ask*. A panel handed the first for a non-repository would render a tree of
    unmarked rows and imply a cleanliness nobody measured.
    """
    root, _ = project
    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    assert body["source"] == "walk"
    assert body["status"] is None


def test_a_status_read_that_fails_still_answers_with_the_files(client, project,
                                                               monkeypatch):
    root, _ = project
    _repo(root)
    monkeypatch.setattr(files_module, "_git_status", lambda _root: None)
    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    assert "README.md" in body["files"]
    assert body["status"] is None


def test_a_rename_does_not_invent_an_entry_for_its_ORIGIN(client, project):
    """Under `-z` a rename record carries its ORIGIN as the next NUL field.

    `R  <to>\\0<from>\\0` — the `<from>` is not a record. A parser that reads it
    as one invents a status entry, and the origin path is chosen here so that the
    invention is not caught by the malformed-record guard: `my file.ts` has a
    space at index 2, so it parses as code `my`, path `file.ts` — a file the
    project does not have, marked with a code git never emitted.

    **This assertion was written twice.** The first version renamed `src/app.ts`,
    and it passed with the origin-consuming line removed — `src/app.ts` has a `c`
    at index 2, so the malformed guard dropped the phantom by luck rather than by
    design. A test that passes against the mutation proves nothing and looks like
    proof forever, so the fixture now names the case the guard cannot save.
    """
    import subprocess
    root, _ = project
    (root / "my file.ts").write_text("const a = 1\n")
    (root / "src" / "zzz.ts").write_text("const z = 1\n")
    _repo(root)
    subprocess.run(["git", "mv", "my file.ts", "renamed.ts"], cwd=str(root),
                   check=True, capture_output=True)
    (root / "src" / "zzz.ts").write_text("const z = 2\n")

    body = client.get("/api/fleet/files", params={"root": str(root)}).json()
    status = body["status"]
    assert status["renamed.ts"].startswith("R")
    # No phantom from the origin field, under either name it could take.
    assert "file.ts" not in status
    assert "my file.ts" not in status
    # And the record that follows the rename keeps its own code.
    assert status["src/zzz.ts"].strip() == "M"


# ─── The typed answer, and the byte route ────────────────────────────────────


def test_a_text_file_with_an_executable_bit_is_still_text(client, project):
    """The bit is not consulted, because reading is not running.

    Measured over 30 session transcripts: 12 distinct existing files were plain
    UTF-8 AND carried `+x`, and were refused at BOTH ends — by the desktop route
    because it would run them, and by this one because the token never reached
    it. Unopenable anywhere in the product.
    """
    import stat as stat_mod

    root, _ = project
    script = root / "deploy.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(script.stat().st_mode | stat_mod.S_IXUSR)

    body = client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": "deploy.sh"}).json()
    assert body["kind"] == "text"
    assert body["content"] == "#!/bin/sh\necho hi\n"


def test_text_with_no_useful_extension_is_still_text(client, project):
    """`Makefile`, `.env`, and a shebang script with no suffix at all.

    None of them has an extension worth asking about, and all three are text.
    The decode attempt is the only test that answers for the file on disk — an
    extension classifier would refuse every one of these while looking correct.
    """
    root, _ = project
    (root / "Makefile").write_text("all:\n\techo hi\n")
    (root / ".env").write_text("KEY=value\n")
    (root / "runner").write_text("#!/usr/bin/env bash\necho hi\n")

    for name in ("Makefile", ".env", "runner"):
        body = client.get("/api/fleet/files/content",
                          params={"root": str(root), "path": name}).json()
        assert body["kind"] == "text", name
        assert body["content"], name


def test_an_svg_takes_the_TEXT_route(client, project):
    """And it is not an omission from the image list — it is the answer.

    An SVG is XML that can carry script, and it is also text: it decodes, so it
    never reaches the binary branch at all. It opens in the editor, which is
    honest — an SVG in a repository is source.
    """
    root, _ = project
    (root / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>\n')
    body = client.get("/api/fleet/files/content",
                      params={"root": str(root), "path": "icon.svg"}).json()
    assert body["kind"] == "text"
    assert "<svg" in body["content"]


def test_a_renderable_binary_is_DESCRIBED_and_its_bytes_have_their_own_route(client, project):
    root, _ = project
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x01\x02" * 8
    (root / "shot.png").write_bytes(png)

    described = client.get("/api/fleet/files/content",
                           params={"root": str(root), "path": "shot.png"}).json()
    assert described["kind"] == "binary"
    assert described["media_type"] == "image/png"
    assert described["bytes"] == len(png)
    assert "content" not in described, "no lossy decode, and no base64 in the JSON"

    raw = client.get("/api/fleet/files/raw",
                     params={"root": str(root), "path": "shot.png"})
    assert raw.status_code == 200
    assert raw.content == png
    assert raw.headers["content-type"].startswith("image/png")


def test_the_bytes_are_not_served_as_something_to_render(client, project):
    """A local dashboard has ONE origin, so the response is never renderable.

    The isolation a second origin would give — the reason GitHub serves user
    content from a separate domain entirely — is not available here, and the
    substitute is that a browser left to itself will not display this body.
    """
    root, _ = project
    (root / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01")
    raw = client.get("/api/fleet/files/raw",
                     params={"root": str(root), "path": "shot.png"})
    assert raw.headers["content-disposition"] == "attachment"
    assert raw.headers["x-content-type-options"] == "nosniff"


def test_a_media_type_off_the_allow_list_serves_NO_bytes(client, project):
    """Not a truncated answer, not a length — nothing.

    The check runs before the file is opened, so a type nobody thought of is
    refused rather than served. An allow-list and a deny-list fail in
    incomparable directions, and this is the one that fails toward silence.
    """
    root, _ = project
    marker = b"PRIVATE-VALUE-DO-NOT-SERVE"
    (root / "report.pdf").write_bytes(b"%PDF-1.4\n\x00" + marker)
    (root / "icon.svg").write_bytes(b"<svg/>" + marker)
    for name in ("report.pdf", "icon.svg"):
        r = client.get("/api/fleet/files/raw", params={"root": str(root), "path": name})
        assert r.status_code == 415, name
        assert marker not in r.content, f"{name}: bytes reached the caller anyway"


def test_the_byte_route_is_confined_exactly_like_the_text_route(client, project, tmp_path):
    """The guard is the FUNCTION, not the endpoint — asserted, not assumed.

    The question to ask of a new route beside a configurable protection is which
    branch it takes OVER, not which one it adds to. This one takes over none:
    every path the text route refuses, it refuses, from the same two calls.
    """
    root, outside = project
    (outside / "secret.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")

    escape = client.get("/api/fleet/files/raw",
                        params={"root": str(root), "path": "../outside/secret.png"})
    assert escape.status_code == 403
    assert escape.json()["detail"] == "access denied"

    link = root / "shortcut.png"
    link.symlink_to(outside / "secret.png")
    through_link = client.get("/api/fleet/files/raw",
                              params={"root": str(root), "path": "shortcut.png"})
    assert through_link.status_code == 403
    assert b"PNG" not in through_link.content

    unregistered = client.get("/api/fleet/files/raw",
                              params={"root": str(outside), "path": "secret.png"})
    assert unregistered.status_code == 400

    absolute = client.get("/api/fleet/files/raw",
                          params={"root": str(root), "path": str(outside / "secret.png")})
    assert absolute.status_code == 403


def test_the_byte_route_has_its_own_cap_and_says_which_one_fired(client, project, monkeypatch):
    """Two caps, because they answer different questions.

    `MAX_BYTES` exists because the editor holds the whole file in a string and a
    write sends it back. A byte stream does neither, and screenshots routinely
    exceed 2 MiB — refusing one *as too large* from a route that only streams it
    would report a limit the framework does not have.
    """
    root, _ = project
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096
    (root / "shot.png").write_bytes(big)
    monkeypatch.setattr(files_module, "MAX_BYTES", 8)

    # Well over the TEXT cap, and served without complaint.
    raw = client.get("/api/fleet/files/raw", params={"root": str(root), "path": "shot.png"})
    assert raw.status_code == 200 and raw.content == big

    monkeypatch.setattr(files_module, "MAX_RAW_BYTES", 8)
    refused = client.get("/api/fleet/files/raw", params={"root": str(root), "path": "shot.png"})
    assert refused.status_code == 413
    assert str(len(big)) in refused.json()["detail"] and "8" in refused.json()["detail"]


def test_a_utf16_file_does_not_reach_the_editor_as_mojibake(client, project):
    """The NUL check, which the decode attempt alone does not catch."""
    root, _ = project
    (root / "notes.txt").write_bytes("hello".encode("utf-16-le"))
    r = client.get("/api/fleet/files/content",
                   params={"root": str(root), "path": "notes.txt"})
    assert r.status_code == 415
    assert r.json()["detail"]["reason"] == "no-view"
