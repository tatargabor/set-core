"""1.3 — a --settings a fán KÍVÜLRŐL viszi a hordozót, és a fába semmi nem íródik."""
import os, tempfile, pty, time, signal, re, subprocess

SP = os.environ.get("PROBE_DIR") or tempfile.mkdtemp(prefix="agent-goal-probe-")
TREE=f"{SP}/tree13"; FW=f"{SP}/fw13"

pid,fd=pty.fork()
if pid==0:
    os.chdir(TREE); os.environ["TERM"]="xterm-256color"
    os.environ.pop("CLAUDE_CODE_CHILD_SESSION",None); os.environ.pop("CLAUDE_CODE_SESSION_ID",None)
    os.execvp("claude",["claude","--model","claude-haiku-4-5-20251001",
                        "--permission-mode","bypassPermissions",
                        "--settings",f"{FW}/settings.json"])
buf=b""
def drain(s):
    global buf
    e=time.time()+s; os.set_blocking(fd,False)
    while time.time()<e:
        try:
            d=os.read(fd,65536)
            if d: buf+=d
        except (BlockingIOError,OSError): pass
        time.sleep(0.04)
drain(6); os.write(fd,b"\r"); drain(8)          # trust
os.write(fd,b"Reply with exactly: OK"); drain(2); os.write(fd,b"\r"); drain(20)
s=re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]","",buf.decode("utf-8","replace"))
print("képernyő farok:", "\n".join(l for l in s.splitlines() if l.strip())[-180:])
os.kill(pid,signal.SIGTERM); time.sleep(1.5)
if os.path.exists(f"/proc/{pid}"): os.kill(pid,signal.SIGKILL)
