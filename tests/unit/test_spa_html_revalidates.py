"""Every HTML document the SPA serves must revalidate.

`/index.html` by name is the same document as `/` and is what the stale-build
probe fetches. Measured 2026-09-21: `/` carried `no-cache`, `/index.html` did
not, so a browser could answer the probe from a heuristically fresh copy.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.server import create_app  # noqa: E402


def test_the_index_revalidates_by_every_name(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "manifest.json").write_text("{}")
    client = TestClient(create_app(str(tmp_path)))
    for url in ("/", "/fleet", "/index.html"):
        assert client.get(url).headers.get("cache-control") == "no-cache", url
    # a non-HTML file keeps its default caching
    assert "cache-control" not in client.get("/manifest.json").headers


def test_an_unknown_api_path_is_a_json_404_not_the_spa(tmp_path):
    """A stale server answered new `/api/` routes with index.html (200), and the
    client reported a JSON parse error instead of a missing route (2026-11-24)."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><html></html>")
    client = TestClient(create_app(str(tmp_path)))
    for url in ("/api/fleet/no-such-route", "/api"):
        r = client.get(url)
        assert r.status_code == 404, url
        assert r.headers["content-type"].startswith("application/json"), url
        assert "restart" in r.json()["hint"], url
    # a client-side route that merely starts with "api" is still the SPA
    assert client.get("/apiary").status_code == 200
