"""Unit tests for set-memoryd daemon components: protocol, client, lifecycle, server."""

import asyncio
import json
import os
import signal
import socket
import tempfile
import time
import threading
import unittest
from unittest.mock import patch, MagicMock

# Add lib to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from set_memoryd.protocol import Request, Response, make_error, make_result, SUPPORTED_METHODS
from set_memoryd.lifecycle import (
    socket_path_for,
    pid_path_for,
    storage_path_for,
    _pid_exists,
    _read_pid,
    _cleanup_stale,
    resolve_project,
)


class TestProtocol(unittest.TestCase):
    """Test JSON-lines protocol serialization."""

    def test_request_to_json(self):
        req = Request(method="recall", params={"query": "auth bug", "limit": 3}, id="abc123")
        data = json.loads(req.to_json())
        self.assertEqual(data["id"], "abc123")
        self.assertEqual(data["method"], "recall")
        self.assertEqual(data["params"]["query"], "auth bug")
        self.assertEqual(data["params"]["limit"], 3)

    def test_request_from_json(self):
        line = '{"id": "x1", "method": "remember", "params": {"content": "hello"}}'
        req = Request.from_json(line)
        self.assertEqual(req.id, "x1")
        self.assertEqual(req.method, "remember")
        self.assertEqual(req.params["content"], "hello")

    def test_request_auto_id(self):
        req = Request(method="health")
        self.assertTrue(len(req.id) > 0)

    def test_response_result(self):
        resp = make_result("r1", [{"id": "mem1", "content": "test"}])
        data = json.loads(resp.to_json())
        self.assertEqual(data["id"], "r1")
        self.assertIn("result", data)
        self.assertNotIn("error", data)
        self.assertTrue(resp.ok)

    def test_response_error(self):
        resp = make_error("r2", "not found")
        data = json.loads(resp.to_json())
        self.assertEqual(data["id"], "r2")
        self.assertEqual(data["error"], "not found")
        self.assertNotIn("result", data)
        self.assertFalse(resp.ok)

    def test_response_from_json_result(self):
        line = '{"id": "r3", "result": {"status": "ok"}}'
        resp = Response.from_json(line)
        self.assertEqual(resp.id, "r3")
        self.assertEqual(resp.result["status"], "ok")
        self.assertIsNone(resp.error)
        self.assertTrue(resp.ok)

    def test_response_from_json_error(self):
        line = '{"id": "r4", "error": "timeout"}'
        resp = Response.from_json(line)
        self.assertFalse(resp.ok)
        self.assertEqual(resp.error, "timeout")

    def test_roundtrip(self):
        req = Request(method="recall", params={"query": "test"}, id="rt1")
        line = req.to_json()
        req2 = Request.from_json(line)
        self.assertEqual(req.id, req2.id)
        self.assertEqual(req.method, req2.method)
        self.assertEqual(req.params, req2.params)

    def test_supported_methods(self):
        self.assertIn("recall", SUPPORTED_METHODS)
        self.assertIn("remember", SUPPORTED_METHODS)
        self.assertIn("proactive_context", SUPPORTED_METHODS)
        self.assertIn("health", SUPPORTED_METHODS)
        self.assertIn("shutdown", SUPPORTED_METHODS)
        self.assertNotIn("invalid_method", SUPPORTED_METHODS)

    def test_request_empty_params(self):
        req = Request(method="health")
        data = json.loads(req.to_json())
        self.assertEqual(data["params"], {})


class TestLifecycle(unittest.TestCase):
    """Test lifecycle path generation and PID utilities."""

    def test_socket_path(self):
        path = socket_path_for("myproject")
        self.assertEqual(path, "/tmp/set-memoryd-myproject.sock")

    def test_pid_path(self):
        path = pid_path_for("myproject")
        self.assertEqual(path, "/tmp/set-memoryd-myproject.pid")

    def test_storage_path(self):
        path = storage_path_for("myproject")
        self.assertIn("myproject", path)
        self.assertIn("memory", path)

    def test_pid_exists_self(self):
        self.assertTrue(_pid_exists(os.getpid()))

    def test_pid_exists_invalid(self):
        self.assertFalse(_pid_exists(0))
        self.assertFalse(_pid_exists(-1))
        # Very high PID unlikely to exist
        self.assertFalse(_pid_exists(4194304))

    def test_read_pid_missing(self):
        self.assertEqual(_read_pid("/nonexistent/pid"), 0)

    def test_read_pid_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pid", delete=False) as f:
            f.write("12345")
            f.flush()
            self.assertEqual(_read_pid(f.name), 12345)
            os.unlink(f.name)

    def test_cleanup_stale_nonexistent(self):
        # Should not raise
        _cleanup_stale("nonexistent-project-xyz")

    def test_resolve_project_outside_git(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td}):
                old_cwd = os.getcwd()
                try:
                    os.chdir(td)
                    result = resolve_project()
                    self.assertIn(result, ("_global", os.path.basename(td)))
                finally:
                    os.chdir(old_cwd)


class TestServerProtocolHandling(unittest.TestCase):
    """Test server request handling with mock MemorySystem."""

    def test_echo_server_roundtrip(self):
        """Start a minimal echo server, send request, verify response."""
        sock_path = f"/tmp/set-memoryd-test-{os.getpid()}.sock"

        async def echo_handler(reader, writer):
            line = await reader.readline()
            req = Request.from_json(line.decode())
            resp = make_result(req.id, {"echo": req.method})
            writer.write((resp.to_json() + "\n").encode())
            await writer.drain()
            writer.close()

        async def run_test():
            if os.path.exists(sock_path):
                os.unlink(sock_path)
            server = await asyncio.start_unix_server(echo_handler, path=sock_path)

            # Client
            reader, writer = await asyncio.open_unix_connection(sock_path)
            req = Request(method="health", id="t1")
            writer.write((req.to_json() + "\n").encode())
            await writer.drain()
            resp_line = await reader.readline()
            resp = Response.from_json(resp_line.decode())

            writer.close()
            server.close()
            await server.wait_closed()
            os.unlink(sock_path)

            return resp

        resp = asyncio.run(run_test())
        self.assertTrue(resp.ok)
        self.assertEqual(resp.result["echo"], "health")
        self.assertEqual(resp.id, "t1")


class TestClientConnection(unittest.TestCase):
    """Test client connection behavior."""

    def test_client_unavailable_raises(self):
        from set_memoryd.client import MemoryClient, DaemonUnavailable

        client = MemoryClient(project="nonexistent-test-project-xyz")
        # Point to a socket that definitely doesn't exist
        client.socket_path = "/tmp/set-memoryd-definitely-nonexistent.sock"
        with self.assertRaises((DaemonUnavailable, Exception)):
            client.request("health")

    def test_client_request_to_echo_server(self):
        """Spin up a minimal server, test client request."""
        sock_path = f"/tmp/set-memoryd-clienttest-{os.getpid()}.sock"
        pid_path = f"/tmp/set-memoryd-clienttest-{os.getpid()}.pid"

        server_ready = threading.Event()
        server_done = threading.Event()

        async def handler(reader, writer):
            line = await reader.readline()
            req = Request.from_json(line.decode())
            resp = make_result(req.id, {"method": req.method, "params": req.params})
            writer.write((resp.to_json() + "\n").encode())
            await writer.drain()
            writer.close()

        async def serve():
            if os.path.exists(sock_path):
                os.unlink(sock_path)
            server = await asyncio.start_unix_server(handler, path=sock_path)
            # Write fake PID
            with open(pid_path, "w") as f:
                f.write(str(os.getpid()))
            server_ready.set()
            # Serve for a bit
            await asyncio.sleep(2)
            server.close()
            await server.wait_closed()
            server_done.set()

        def run_server():
            asyncio.run(serve())

        t = threading.Thread(target=run_server, daemon=True)
        t.start()
        server_ready.wait(timeout=3)

        try:
            from set_memoryd.client import MemoryClient
            # Patch is_running to return True (our test server has a valid socket)
            project = f"clienttest-{os.getpid()}"
            client = MemoryClient(project=project)
            # Socket path matches our test server
            client.socket_path = sock_path

            result = client.request("recall", {"query": "test", "limit": 3})
            self.assertEqual(result["method"], "recall")
            self.assertEqual(result["params"]["query"], "test")
        finally:
            for p in (sock_path, pid_path):
                try:
                    os.unlink(p)
                except FileNotFoundError:
                    pass


if __name__ == "__main__":
    unittest.main()
