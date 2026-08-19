"""1.1 + 1.2 — hook-payloadok, és a forduló-állapot jelöltjei MINDKÉT irányban.

A szonda egy lassú fordulót indít (Bash sleep), és közben MINTAVÉTELEZ: mid-turn és
utána. Egy jel csak akkor használható, ha a két minta eltér.
"""
import os, tempfile, pty, time, glob, signal, json, re, subprocess

SP = os.environ.get("PROBE_DIR") or tempfile.mkdtemp(prefix="agent-goal-probe-")
WORK=f"{SP}/hookprobe"
LOGDIR=os.path.expanduser("~/.claude/projects/"+WORK.replace("/","-"))
os.makedirs(WORK, exist_ok=True)

pid,fd=pty.fork()
if pid==0:
    os.chdir(WORK); os.environ["TERM"]="xterm-256color"
    os.environ.pop("CLAUDE_CODE_CHILD_SESSION",None); os.environ.pop("CLAUDE_CODE_SESSION_ID",None)
    os.execvp("claude",["claude","--model","claude-haiku-4-5-20251001","--permission-mode","bypassPermissions"])

buf=b""
def drain(s):
    global buf
    e=time.time()+s; os.set_blocking(fd,False)
    while time.time()<e:
        try:
            d=os.read(fd,65536)
            if d: buf+=d
        except (BlockingIOError,OSError): pass
        time.sleep(0.03)
def screen(n=400):
    s=re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]","",buf.decode("utf-8","replace"))
    s=re.sub(r"\x1b\][^\x07]*\x07","",s)
    return "\n".join(l for l in s.splitlines() if l.strip())[-n:]

def transcript():
    fs=glob.glob(LOGDIR+"/*.jsonl")
    if not fs: return None
    f=max(fs,key=os.path.getmtime)
    rows=[]
    for l in open(f,errors="replace"):
        l=l.strip()
        if l:
            try: rows.append(json.loads(l))
            except Exception: pass
    return f,rows

def sample(tag):
    """egy pillanatkép minden jelöltről"""
    t=transcript()
    last=None; nrows=0; pend=None
    if t:
        f,rows=t; nrows=len(rows)
        for r in reversed(rows):
            if r.get("type") in ("user","assistant","system"):
                m=r.get("message") or {}
                c=m.get("content")
                kind=r.get("type")
                if isinstance(c,list) and c:
                    kind+= "/"+ (c[-1].get("type") if isinstance(c[-1],dict) else "?")
                last=kind; break
        for r in reversed(rows):
            if "pendingBackgroundAgentCount" in r: pend=r["pendingBackgroundAgentCount"]; break
    scr=screen(220)
    print(f"[{tag}] napló-sorok={nrows} utolsó-sor={last} pending={pend}")
    print(f"[{tag}] képernyő-farok: {scr[-160:]!r}")
    return dict(tag=tag, rows=nrows, last=last, pend=pend, screen=scr)

drain(6)
os.write(fd,b"\r")   # a "trust this folder" kérdés megválaszolása
drain(8)
print("=== indulás után ===")
s0=sample("ELŐTTE-idle")

os.write(fd,b"Run this exact bash command and then say DONE: sleep 12")
drain(2); os.write(fd,b"\r")
drain(6)
print("=== forduló KÖZBEN (a sleep alatt) ===")
s1=sample("KOZBEN-busy")
drain(4); s1b=sample("KOZBEN-busy-2")

drain(25)
print("=== forduló UTÁN ===")
s2=sample("UTANA-idle")

json.dump([s0,s1,s1b,s2],open(f"{SP}/hookout/samples.json","w"),ensure_ascii=False,indent=1)
os.kill(pid,signal.SIGTERM); time.sleep(1)
if os.path.exists(f"/proc/{pid}"): os.kill(pid,signal.SIGKILL)
