"""Speak MCP to this checkout's set-core server once (design D3).

The server is one program for every project; what differs per project is its
registration, which is checked statically elsewhere. So the live probe runs once,
with CLAUDE_PROJECT_DIR set to a throwaway one-file repository: a real project
would turn the probe into a measurement of its index refresh (67 s measured on a
large one), which is `set-kb doctor`'s question, not the server's.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import tempfile
import threading
import time

logger = logging.getLogger(__name__)

MARKER = "setdoctorprobeword"


def _throwaway_repo(base: str) -> str:
    repo = os.path.join(base, "probe-repo")
    os.makedirs(repo)
    with open(os.path.join(repo, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(".set/\n")
    with open(os.path.join(repo, "note.md"), "w", encoding="utf-8") as f:
        f.write(f"# Probe\n\n{MARKER} " + "word " * 30 + "\n")
    subprocess.run(["git", "init", "-q", repo], check=True, capture_output=True, timeout=30)
    return repo


def probe(server_dir: str, timeout: float = 90.0) -> tuple:
    """(ok, detail). Starts `uv --directory <server_dir> run python set_mcp_server.py`,
    sends initialize + tools/call kb_search, and stops it. Never raises."""
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="set-doctor-") as tmp:
        try:
            repo = _throwaway_repo(tmp)
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"could not create the probe repository: {e}"
        env = {**os.environ, "CLAUDE_PROJECT_DIR": repo}
        cmd = ["uv", "--directory", server_dir, "run", "python", "set_mcp_server.py"]
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env)
        except OSError as e:
            return False, f"could not start the server: {e}"
        logger.info("mcp probe: started pid=%s in %s", proc.pid, server_dir)
        lines: "queue.Queue" = queue.Queue()
        threading.Thread(target=lambda: [lines.put(ln) for ln in proc.stdout] + [lines.put(None)],
                         daemon=True).start()
        err_tail: list = []
        threading.Thread(target=lambda: [err_tail.append(ln) for ln in proc.stderr], daemon=True).start()

        def send(msg: dict) -> None:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        def recv(want: int) -> dict:
            while True:
                left = timeout - (time.time() - started)
                if left <= 0:
                    raise TimeoutError(f"no answer within {timeout:.0f} s")
                try:
                    line = lines.get(timeout=left)
                except queue.Empty:
                    raise TimeoutError(f"no answer within {timeout:.0f} s") from None
                if line is None:
                    raise EOFError("the server exited")
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue  # a stray non-protocol line
                if msg.get("id") == want:
                    return msg

        try:
            send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "set-doctor", "version": "1"}}})
            info = recv(1).get("result", {}).get("serverInfo", {})
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "kb_search", "arguments": {"query": MARKER, "limit": 1, "linked": False}}})
            res = recv(2)
            if "error" in res:
                return False, f"kb_search returned an error: {res['error'].get('message', res['error'])}"
            content = (res.get("result") or {}).get("content") or [{}]
            text = content[0].get("text", "")
            try:
                page = json.loads(text)
            except ValueError:
                return False, f"kb_search did not return a search page: {text[:200]}"
            paths = [h.get("path") for h in page.get("hits", [])]
            if "note.md" not in paths:
                return False, f"kb_search answered but did not find the probe file (hits: {paths})"
            took = time.time() - started
            return True, f"{info.get('name', '?')} {info.get('version', '')} answered kb_search in {took:.1f} s"
        except (TimeoutError, EOFError, OSError, ValueError) as e:
            tail = "".join(err_tail[-5:]).strip().replace("\n", " | ")
            logger.warning("mcp probe failed: %s; stderr tail: %s", e, tail)
            return False, f"{e}" + (f" — server stderr: {tail[-400:]}" if tail else "")
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            logger.info("mcp probe: stopped pid=%s rc=%s", proc.pid, proc.returncode)
