---
name: gui-tester
description: Run GUI tests and report results. Use after GUI changes to verify nothing is broken.
tools: Bash, Read, Grep, Glob
model: haiku
maxTurns: 5
---

Run the GUI test suite and report results concisely.

**Command:**
```bash
PYTHONPATH=. python -m pytest tests/gui/ -v --tb=short
```

**Report format:**
- Total: X passed, Y failed, Z errors
- For each failure: test name + one-line reason
- If all pass: just say "All X tests passed"
