"""1.4 — a /clear forgatás a keret VALÓDI argv-jével (DEFAULT_AGENT_ARGV), nem a szonda Haikujával.

A folyamat-azonosságot a starttime jegy dönti el, nem a pid: a pid újrahasznosul.
"""
import os, tempfile, pty, time, glob, signal, re, json

SP = os.environ.get("PROBE_DIR") or tempfile.mkdtemp(prefix="agent-goal-probe-")
WORK=f"{SP}/rot14"
LOGDIR=os.path.expanduser("~/.claude/projects/"+WORK.replace("/","-"))
ARGV=["claude","--dangerously-skip-permissions"]     # lib/set_orch/fleet/ownerd.py:65

def ident(pid):
    try:
        st=open(f"/proc/{pid}/stat").read().rsplit(")",1)[1].split()
        return st[19]          # starttime jegy — ez azonosítja a FOLYAMATOT
    except Exception: return None
def logs(): return sorted(glob.glob(LOGDIR+"/*.jsonl"))

pid,fd=pty.fork()
if pid==0:
    os.chdir(WORK); os.environ["TERM"]="xterm-256color"
    os.environ.pop("CLAUDE_CODE_CHILD_SESSION",None); os.environ.pop("CLAUDE_CODE_SESSION_ID",None)
    os.execvp(ARGV[0],ARGV)
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
def scr(n=260):
    s=re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]","",buf.decode("utf-8","replace"))
    s=re.sub(r"\x1b\][^\x07]*\x07","",s)
    return "\n".join(l for l in s.splitlines() if l.strip())[-n:]

drain(7); os.write(fd,b"\r"); drain(8)              # trust
print("argv:",ARGV)
id0=ident(pid); print(f"indulás: pid={pid} starttime={id0}")

os.write(fd,b"Reply with exactly: ONE"); drain(2); os.write(fd,b"\r"); drain(30)
l1=logs(); print(f"1. forduló után naplók: {len(l1)} → {[os.path.basename(x) for x in l1]}")

os.write(fd,b"/clear"); drain(2); os.write(fd,b"\r"); drain(8)
os.write(fd,b"Reply with exactly: TWO"); drain(2); os.write(fd,b"\r"); drain(30)
l2=logs(); id1=ident(pid)
print(f"--- /clear UTÁN ---")
print(f"naplók: {len(l2)} → {[os.path.basename(x) for x in l2]}")
print(f"pid={pid} él={os.path.exists(f'/proc/{pid}')} starttime={id1}  AZONOS_FOLYAMAT={id0==id1 and id0 is not None}")
print("képernyő:", scr())
# a modell, amivel valóban futott
if l2:
    rows=[json.loads(x) for x in open(l2[-1],errors="replace") if x.strip()]
    models={r.get("message",{}).get("model") for r in rows if isinstance(r.get("message"),dict)}
    print("modell a naplóban:", {m for m in models if m})
os.kill(pid,signal.SIGTERM); time.sleep(1.5)
if os.path.exists(f"/proc/{pid}"): os.kill(pid,signal.SIGKILL)
