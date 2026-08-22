"""The paste store — where it writes, what it refuses, and what it forgets.

Two things decide whether this file is worth anything.

**It must prove the store writes OUTSIDE every project tree.** That is not a
detail of the design; it is the reason the module exists apart from `files.py`.
So the tests walk a real project tree before and after and assert it is
byte-identical, rather than asserting the returned path merely "looks right" —
a path that looks right is a claim about a string, and the requirement is about
a filesystem.

**And it must prove the caller cannot steer any of it.** The stored name is
derived from the content; a caller-supplied name is DISCARDED rather than
sanitised, which removes the traversal class instead of defending against it.
A test that only tried `../` would pass against a sanitiser that still lets the
caller pick the name.

Everything runs against a real `tmp_path` store with real files, for the reason
the sibling file states: a guard tested against a mock is tested against the
assumptions of whoever wrote the mock.
"""

import hashlib
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient
from set_orch.server import create_app
from set_orch.api import paste as paste_module


def png(payload: bytes = b"x") -> bytes:
    """A byte string that IS a PNG as far as any sniffer is concerned.

    Deliberately NOT compressed. The first version of this helper ran the payload
    through `zlib`, and the ceiling test then posted a "4000 byte" image that was
    forty bytes on the wire — so the endpoint correctly accepted it and the test
    read that as the ceiling failing to fire. A fixture whose size does not match
    the number in the test name is a measurement of something else.
    """
    return b"\x89PNG\r\n\x1a\n" + payload


JPEG = b"\xff\xd8\xff\xe0" + b"jfif-body"
GIF = b"GIF89a" + b"gif-body"
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"vp8-body"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """The store root, redirected — patched on the module the endpoint asks."""
    root = tmp_path / "store"
    monkeypatch.setattr(paste_module, "store_root", lambda: root)
    return root


@pytest.fixture
def project(tmp_path):
    """A project tree that nothing in this feature is allowed to touch."""
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.ts").write_text("const a = 1\n")
    (root / "README.md").write_text("# hello\n")
    return root


def snapshot(root):
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            p = os.path.join(dirpath, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


@pytest.fixture
def client(store):
    return TestClient(create_app(web_dist_dir=None))


# ─── Where it writes ─────────────────────────────────────────────────────────


def test_a_stored_image_lands_in_the_store_and_nowhere_near_a_project(
    client, store, project
):
    before = snapshot(project)
    r = client.post("/api/fleet/paste", content=png(), headers={"content-type": "image/png"})
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    assert os.path.isfile(path)
    assert os.path.realpath(path).startswith(os.path.realpath(store) + os.sep)
    # The requirement is about a filesystem, so the check is too: the project is
    # byte-identical, not merely "not mentioned in the response".
    assert snapshot(project) == before
    assert os.path.relpath(path, project).startswith("..")


def test_the_request_cannot_choose_where_the_file_goes(client, store, project):
    """Every field a caller could steer with, tried at once.

    The endpoint takes raw bytes and no destination field at all, so this test
    is really asking: did anybody ADD one? A future 'convenience' parameter would
    turn this feature into a project writer, which is the operation class the
    framework's safety work closed.
    """
    r = client.post(
        "/api/fleet/paste",
        content=png(),
        headers={
            "content-type": "image/png",
            "x-path": str(project / "pwned.png"),
            "x-filename": "../../pwned.png",
            "content-disposition": 'attachment; filename="../../pwned.png"',
        },
    )
    assert r.status_code == 200, r.text
    assert os.path.realpath(r.json()["path"]).startswith(os.path.realpath(store) + os.sep)
    assert not (project / "pwned.png").exists()
    assert list(store.iterdir())  # something WAS stored — this is not a vacuous pass


# ─── The name ────────────────────────────────────────────────────────────────


def test_a_caller_supplied_name_reaches_no_part_of_the_path(client, store):
    hostile = '../../etc/pwned\x00.png"; rm -rf /'
    r = client.post(
        "/api/fleet/paste",
        content=png(b"named"),
        headers={"content-type": "image/png", "x-filename": hostile},
    )
    assert r.status_code == 200, r.text
    name = os.path.basename(r.json()["path"])
    assert name == hashlib.sha256(png(b"named")).hexdigest() + ".png"
    for fragment in ("..", "etc", "pwned", "rm"):
        assert fragment not in name


def test_the_same_bytes_twice_answer_with_the_same_usable_path(client, store):
    a = client.post("/api/fleet/paste", content=png(b"dup"), headers={"content-type": "image/png"})
    b = client.post("/api/fleet/paste", content=png(b"dup"), headers={"content-type": "image/png"})
    assert a.status_code == b.status_code == 200
    assert a.json()["path"] == b.json()["path"]
    assert os.path.isfile(b.json()["path"])
    assert len(list(store.iterdir())) == 1


# ─── What it accepts ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "data,ext",
    [(png(), ".png"), (JPEG, ".jpg"), (GIF, ".gif"), (WEBP, ".webp")],
)
def test_every_accepted_type_is_stored_under_its_own_extension(client, store, data, ext):
    r = client.post("/api/fleet/paste", content=data, headers={"content-type": "image/png"})
    assert r.status_code == 200, r.text
    assert r.json()["path"].endswith(ext)


def test_a_type_that_is_not_an_image_is_refused_and_writes_nothing(client, store):
    r = client.post(
        "/api/fleet/paste", content=b"%PDF-1.7\nnot an image", headers={"content-type": "application/pdf"}
    )
    assert r.status_code == 415
    assert "image" in r.json()["detail"].lower()
    assert not store.exists() or not list(store.iterdir())


def test_a_declared_image_carrying_other_bytes_is_refused(client, store):
    """The declared type is the caller's claim; the bytes are the fact.

    Trusting the header would make the type check a statement about the REQUEST
    while the requirement is about what landed on disk — and it is the shape a
    reviewer is least likely to notice, because the code reads as a type check.
    """
    r = client.post(
        "/api/fleet/paste", content=b"#!/bin/sh\nrm -rf /\n", headers={"content-type": "image/png"}
    )
    assert r.status_code == 415
    assert not store.exists() or not list(store.iterdir())


def test_content_over_the_item_limit_is_refused_with_the_limit_named(client, store):
    big = png() + b"\x00" * paste_module.MAX_ITEM_BYTES
    r = client.post("/api/fleet/paste", content=big, headers={"content-type": "image/png"})
    assert r.status_code == 413
    assert str(paste_module.MAX_ITEM_BYTES) in r.json()["detail"]
    assert not store.exists() or not list(store.iterdir())


# ─── The bounds ──────────────────────────────────────────────────────────────


def test_an_entry_past_the_maximum_age_is_gone_after_the_next_use(client, store):
    r = client.post("/api/fleet/paste", content=png(b"old"), headers={"content-type": "image/png"})
    old = r.json()["path"]
    stale = time.time() - paste_module.MAX_AGE_SECONDS - 60
    os.utime(old, (stale, stale))

    r2 = client.post("/api/fleet/paste", content=png(b"new"), headers={"content-type": "image/png"})
    assert r2.status_code == 200
    assert not os.path.exists(old)
    assert os.path.isfile(r2.json()["path"])


def test_expiry_is_computed_from_disk_so_a_stopped_framework_changes_nothing(store):
    """No process was running when the entry should have expired.

    The sweep takes its answer from the files' own mtimes, so there is nothing
    for a timer to have missed — which is the property a background task could
    not have offered.
    """
    store.mkdir(parents=True)
    stale = store / "stale.png"
    stale.write_bytes(png(b"stale"))
    t = time.time() - paste_module.MAX_AGE_SECONDS - 1
    os.utime(stale, (t, t))
    paste_module.sweep(store)
    assert not stale.exists()


def test_reaching_the_ceiling_evicts_oldest_first(client, store, monkeypatch):
    monkeypatch.setattr(paste_module, "MAX_STORE_BYTES", 4096)
    paths = []
    for i in range(3):
        body = png(b"x" * 1000 + bytes([i]))
        r = client.post("/api/fleet/paste", content=body, headers={"content-type": "image/png"})
        assert r.status_code == 200, r.text
        p = r.json()["path"]
        os.utime(p, (1000 + i, 1000 + i))  # a definite age order
        paths.append(p)

    r = client.post(
        "/api/fleet/paste", content=png(b"y" * 3000), headers={"content-type": "image/png"}
    )
    assert r.status_code == 200, r.text
    assert not os.path.exists(paths[0]), "the oldest entry should have gone first"
    assert os.path.isfile(r.json()["path"])


def test_an_item_that_still_does_not_fit_is_refused_with_the_ceiling_named(
    client, store, monkeypatch
):
    monkeypatch.setattr(paste_module, "MAX_STORE_BYTES", 512)
    r = client.post(
        "/api/fleet/paste", content=png(b"z" * 4000), headers={"content-type": "image/png"}
    )
    assert r.status_code == 507
    assert "512" in r.json()["detail"]


# ─── What it must not remember ───────────────────────────────────────────────


def test_no_log_line_carries_a_name_or_the_content(client, store, caplog):
    """A pasted image is a consumer's content — the log gets the SHAPE only.

    Both directions are checked, because a log that says nothing at all would
    also pass a test that only looked for the absence of a name.
    """
    caplog.set_level("INFO", logger="set_orch.api.paste")
    secret = b"CUSTOMER-VALUE-DO-NOT-LOG"
    r = client.post(
        "/api/fleet/paste",
        content=png(secret),
        headers={"content-type": "image/png", "x-filename": "acme-invoice.png"},
    )
    assert r.status_code == 200
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "image/png" in text and "outcome=ok" in text  # the shape IS logged
    stored = os.path.basename(r.json()["path"])
    for forbidden in ("acme-invoice", stored, "CUSTOMER-VALUE"):
        assert forbidden not in text


def test_a_refusal_names_the_rule_and_nothing_from_the_content(client, store, caplog):
    caplog.set_level("INFO", logger="set_orch.api.paste")
    client.post(
        "/api/fleet/paste",
        content=b"CUSTOMER-VALUE-DO-NOT-LOG in a text file",
        headers={"content-type": "image/png", "x-filename": "acme.txt"},
    )
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "rule=type" in text
    for forbidden in ("acme", "CUSTOMER-VALUE"):
        assert forbidden not in text
