"""A project's own declared pages: where they are read from, and the up/down check.

The check is driven against a real local HTTP server and a real closed port, not a mock: what
it has to tell apart is a page that answers and a port nobody listens on.
"""

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.testclient import TestClient  # noqa: E402

from set_orch.api import helpers as api_helpers  # noqa: E402
from set_orch.fleet import project_pages as pp  # noqa: E402
from set_orch.server import create_app  # noqa: E402


class _Ok(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"Zq7-page-body-must-not-leak"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Ok)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@pytest.fixture
def closed_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()            # nobody listens here now
    return f"http://127.0.0.1:{port}/"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "config"))
    pp.clear_cache()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    reg = tmp_path / "projects.json"
    reg.write_text(json.dumps([{"name": "alpha", "path": str(a)}, {"name": "beta", "path": str(b)}]))
    monkeypatch.setattr(api_helpers, "PROJECTS_FILE", reg)

    class Env:
        root = tmp_path
        alpha = a
        beta = b
        projects = [{"name": "alpha", "path": str(a)}, {"name": "beta", "path": str(b)}]
    yield Env()
    pp.clear_cache()


def test_a_manifest_without_a_command_still_declares_pages(env):
    (env.alpha / ".set-endpoint.json").write_text(json.dumps(
        {"pages": [{"name": "Queue", "url": "http://127.0.0.1:1/", "description": "replies"}]}))
    pages, bad = pp.declared_pages(env.projects)
    assert [(p.project, p.name, p.source, p.description) for p in pages] == [("alpha", "Queue", "manifest", "replies")]
    assert bad == 0


def test_local_config_declares_pages_and_wins_by_name(env):
    from set_orch import local_config
    (env.alpha / ".set-endpoint.json").write_text(json.dumps(
        {"pages": [{"name": "Queue", "url": "http://127.0.0.1:1/"}, {"name": "Docs", "url": "http://127.0.0.1:2/"}]}))
    local_config.set_value("pages", json.dumps([{"name": "Queue", "url": "http://127.0.0.1:9/"}]), project="alpha")
    local_config.set_value("pages", [{"name": "Only-local", "url": "https://example.test/"}], project="beta")
    by = {(p.project, p.name): p for p in pp.declared_pages(env.projects)[0]}
    assert by[("alpha", "Queue")].url == "http://127.0.0.1:9/" and by[("alpha", "Queue")].source == "local"
    assert by[("alpha", "Docs")].source == "manifest"
    assert by[("beta", "Only-local")].url == "https://example.test/"


def test_malformed_pages_are_skipped_and_counted(env):
    (env.alpha / ".set-endpoint.json").write_text(json.dumps({"pages": [
        {"name": "ok", "url": "http://127.0.0.1:1/"},
        {"name": "no scheme", "url": "127.0.0.1:1"},
        {"name": "file", "url": "file:///etc/passwd"},
        {"url": "http://127.0.0.1:1/"},
        "just text",
    ]}))
    pages, bad = pp.declared_pages(env.projects)
    assert [p.name for p in pages] == ["ok"] and bad == 4


def test_a_page_that_answers_is_up_and_a_closed_port_is_down(env, server, closed_url):
    up = pp.probe(server)
    down = pp.probe(closed_url)
    assert up["up"] is True and up["status"] == 200
    assert down["up"] is False and down["status"] is None and down["error"]


def test_the_api_lists_pages_with_their_state_and_never_a_body(env, server, closed_url, caplog):
    (env.alpha / ".set-endpoint.json").write_text(json.dumps({"pages": [
        {"name": "Live", "url": server}, {"name": "Dead", "url": closed_url}]}))
    client = TestClient(create_app(web_dist_dir=None))
    with caplog.at_level("DEBUG"):
        data = client.get("/api/fleet/pages").json()
    by = {p["name"]: p for p in data["pages"]}
    assert by["Live"]["up"] is True and by["Dead"]["up"] is False
    assert data["down"] == 1
    assert "Zq7-page-body-must-not-leak" not in json.dumps(data)
    assert "Zq7-page-body-must-not-leak" not in caplog.text


def test_a_probe_is_cached_briefly(env, server):
    first = pp.probe(server, now=1000.0)
    again = pp.probe(server, now=1010.0)
    assert again is first
    later = pp.probe(server, now=1000.0 + pp.PROBE_CACHE_S + 1)
    assert later is not first
