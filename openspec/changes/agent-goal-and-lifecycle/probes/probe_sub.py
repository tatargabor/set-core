import os, tempfile, pty, time, glob, signal, re
SP = os.environ.get("PROBE_DIR") or tempfile.mkdtemp(prefix="agent-goal-probe-")
WORK=f"{SP}/clearprobe"
LOGDIR=os.path.expanduser("~/.claude/projects/"+WORK.replace("/","-"))
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
        time.sleep(0.05)
drain(10)
os.write(fd,b"Task tool: spawn one general-purpose subagent to return 2+2. Nothing else.")
drain(3)
os.write(fd,b"\r")
drain(80)
s=re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]","",buf.decode("utf-8","replace"))
print("--- képernyő vége ---"); print("\n".join(l for l in s.splitlines() if l.strip())[-500:])
print("naplók:",[os.path.basename(x) for x in glob.glob(LOGDIR+"/*.jsonl")])
os.kill(pid,signal.SIGTERM); time.sleep(1)
if os.path.exists(f"/proc/{pid}"): os.kill(pid,signal.SIGKILL)
