"""1.2 — a forduló-állapot jelöltjei, másodpercenként mintavételezve, KÉT fordulón:
   egy eszközhívásos (lassú) és egy tisztán szöveges (gyors).
Egy jel csak akkor jó, ha BUSY-t mond forduló közben ÉS IDLE-t a várakozáskor.
"""
import os, tempfile, pty, time, glob, signal, json, re

SP = os.environ.get("PROBE_DIR") or tempfile.mkdtemp(prefix="agent-goal-probe-")
WORK=f"{SP}/hookprobe"
LOGDIR=os.path.expanduser("~/.claude/projects/"+WORK.replace("/","-"))

pid,fd=pty.fork()
if pid==0:
    os.chdir(WORK); os.environ["TERM"]="xterm-256color"
    os.environ.pop("CLAUDE_CODE_CHILD_SESSION",None); os.environ.pop("CLAUDE_CODE_SESSION_ID",None)
    os.execvp("claude",["claude","--model","claude-haiku-4-5-20251001","--permission-mode","bypassPermissions"])

buf=b""
def pump():
    global buf
    os.set_blocking(fd,False)
    try:
        d=os.read(fd,65536)
        if d: buf+=d
    except (BlockingIOError,OSError): pass
def drain(s):
    e=time.time()+s
    while time.time()<e: pump(); time.sleep(0.03)

def tail_type():
    fs=glob.glob(LOGDIR+"/*.jsonl")
    if not fs: return None
    f=max(fs,key=os.path.getmtime)
    last=None
    for l in open(f,errors="replace"):
        l=l.strip()
        if not l: continue
        try: r=json.loads(l)
        except Exception: continue
        t=r.get("type")
        if t in ("user","assistant"):
            m=r.get("message") or {}; c=m.get("content")
            sub = c[-1].get("type") if isinstance(c,list) and c and isinstance(c[-1],dict) else "text?"
            last=f"{t}/{sub}"
        elif t: last=t
    return last

def hook_state(now):
    """a legutolsó hook-esemény a mintavétel PILLANATA előtt"""
    evs=[]
    for n in ("UserPromptSubmit","Stop"):
        p=f"{SP}/hookout/{n}.jsonl"
        if os.path.exists(p):
            for l in open(p):
                ts=float(l.split("\t",1)[0])
                if ts<=now: evs.append((ts,n))
    if not evs: return "nincs-esemény"
    evs.sort()
    return "BUSY" if evs[-1][1]=="UserPromptSubmit" else "IDLE"

samples=[]
def sample(truth):
    now=time.time()
    s=dict(t=now, truth=truth, tail=tail_type(), hooks=hook_state(now))
    samples.append(s); return s

drain(6); os.write(fd,b"\r"); drain(8)   # trust prompt
for _ in range(3): sample("IDLE"); drain(1)

os.write(fd,b"Run this exact bash command then say DONE: sleep 14"); drain(2); os.write(fd,b"\r")
t_end=time.time()+16
while time.time()<t_end: sample("BUSY"); drain(1)
drain(14)
for _ in range(4): sample("IDLE"); drain(1)

os.write(fd,b"Reply with exactly the word ALPHA and nothing else"); drain(2); os.write(fd,b"\r")
t_end=time.time()+4
while time.time()<t_end: sample("BUSY?"); drain(0.7)
drain(12)
for _ in range(3): sample("IDLE"); drain(1)

json.dump(samples,open(f"{SP}/hookout/turnsamples.json","w"),indent=1)
os.kill(pid,signal.SIGTERM); time.sleep(1)
if os.path.exists(f"/proc/{pid}"): os.kill(pid,signal.SIGKILL)
print("minták:",len(samples))
