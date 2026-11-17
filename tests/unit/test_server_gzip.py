"""B-181: the dashboard server compresses large JSON and leaves streams alone.

`/api/fleet/agents` was measured at ~200 KB raw, polled every ~5 s per open
tab, with no compression at all. These tests drive the real app factory, so
removing the middleware from `create_app` turns the first one red.
"""

import gzip
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from set_orch.server import create_app


def _app_with_probe_routes():
    app = create_app(web_dist_dir="/nonexistent")
    big = {"rows": [{"name": f"agent-{i}", "cwd": "/x/y/z", "state": "idle"} for i in range(2000)]}

    @app.get("/__test/big")
    async def _big():
        return big

    @app.get("/__test/small")
    async def _small():
        return {"ok": True}

    @app.get("/__test/stream")
    async def _stream():
        async def gen():
            for i in range(200):
                yield f"data: {'x' * 50} {i}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    # The SPA catch-all is absent (no dist dir), so the probe routes are reachable.
    return app, big


def test_large_json_is_gzipped_when_client_accepts_it():
    app, big = _app_with_probe_routes()
    client = TestClient(app)
    r = client.get("/__test/big", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    # The wire size must actually shrink, not only carry the header.
    assert int(r.headers["content-length"]) < len(r.content) / 4
    assert r.json() == big


def test_client_without_gzip_gets_identity():
    app, big = _app_with_probe_routes()
    client = TestClient(app)
    r = client.get("/__test/big", headers={"Accept-Encoding": "identity"})
    assert r.headers.get("content-encoding") is None
    assert r.json() == big


def test_small_response_is_not_compressed():
    app, _ = _app_with_probe_routes()
    client = TestClient(app)
    r = client.get("/__test/small", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") is None


def test_event_stream_is_never_compressed():
    """A gzipped SSE stream is buffered until a compression block fills, so the
    follower would see nothing for seconds. Starlette excludes the type; this
    holds it in case the middleware or its version changes."""
    app, _ = _app_with_probe_routes()
    client = TestClient(app)
    r = client.get("/__test/stream", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") is None
    assert r.text.startswith("data: ")
    # And it is not secretly gzip bytes under a missing header.
    try:
        gzip.decompress(r.content)
        raise AssertionError("stream body is gzip despite no content-encoding")
    except OSError:
        pass
