#!/usr/bin/env python3
"""probe_subagent_model — which model actually answers a `model: sonnet` subagent?

Two live probes, one per provider. Both reproduce the exact path a framework
subagent takes when its agent definition pins an Anthropic short name —
`.claude/agents/code-reviewer.md` declares `model: sonnet`, and B-115 measured
that such a subagent picks its model INSIDE the running CLI, after launch, so
only the environment can steer it:

    claude  resolve(provider="anthropic") -> clean env, `--model sonnet`
            must answer from a Claude Sonnet id.

    glm     resolve(provider="glm")       -> GLM endpoint + alias env,
            `--model sonnet` is rewritten through
            ANTHROPIC_DEFAULT_SONNET_MODEL and must answer glm-5.3-flash.

The measurement is the API RESPONSE's model field (`--output-format json`),
never the agent's self-report — a model asked "which model are you" answers
from its prompt, not its wiring.

⚠ Each probe makes one REAL API call. This file is deliberately NOT named
`test_*`: no pytest run may ever collect it and spend money uninvited. Run it
by hand:

    python3 tests/live/probe_subagent_model.py           # both providers
    python3 tests/live/probe_subagent_model.py glm       # one provider

Requires `claude` on PATH and the machine's `~/.config/set-core/providers.json`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from set_orch.providers import resolve  # noqa: E402

PROMPT = "Reply with ONE word: OK"
#: The short name a subagent's definition pins (`code-reviewer: sonnet`). This
#: is the whole probe: under glm it survives only if the alias env reaches the
#: child; under claude it survives only if the ambient GLM alias variables do
#: NOT reach it (B-116).
SUBAGENT_MODEL = "sonnet"


def child_env(plan) -> dict:
    """The environment a start path builds: ambient minus `unset`, plus `env`."""
    env = {k: v for k, v in os.environ.items() if k not in plan.unset}
    env.update(plan.env)
    return env


def probe(provider: str, model_assert) -> bool:
    plan = resolve(provider=provider)
    print(f"[{provider}] {plan.describe()}")
    print(f"[{provider}] unset: {', '.join(plan.unset)}")

    cmd = ["claude", "-p", PROMPT, "--model", SUBAGENT_MODEL,
           "--output-format", "json"]
    try:
        run = subprocess.run(cmd, env=child_env(plan), capture_output=True,
                             text=True, timeout=300, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        print(f"FAIL [{provider}] no response within 300s")
        return False
    if run.returncode != 0:
        print(f"FAIL [{provider}] exit {run.returncode}: "
              f"{run.stderr.strip()[:300] or run.stdout.strip()[:300]}")
        return False
    try:
        result = json.loads(run.stdout)
    except json.JSONDecodeError:
        print(f"FAIL [{provider}] output is not JSON: {run.stdout[:300]}")
        return False
    # The answering model lives in `modelUsage` — one entry per model that
    # served any part of the call. There is no top-level `model` field, and an
    # assertion on a missing field would be a vacuous pass, so an EMPTY
    # modelUsage is a failure by construction.
    served = sorted(result.get("modelUsage", {}).keys())
    if not served:
        print(f"FAIL [{provider}] no modelUsage in the response — "
              "cannot say what answered")
        return False
    # `modelUsage` also lists the CLI's OWN auxiliary calls (a `claude -p` run
    # makes an internal haiku request for session bookkeeping), so the property
    # is asserted on the LIST: the requested model's family must be present,
    # and NOTHING foreign may have served — a leaked alias shows up exactly
    # there, as a model from another vendor in this list.
    ok = model_assert(served)
    verdict = "PASS" if ok else "FAIL"
    print(f"{verdict} [{provider}] --model {SUBAGENT_MODEL} was served by: "
          f"{', '.join(served)}")
    return ok


def main(argv: list[str]) -> int:
    # `claude` is accepted on the command line and resolves to the provider the
    # config declares as `anthropic` — the config's name is what `resolve()`
    # requires, the CLI's name is what a person types.
    cases = {
        # every served model is Claude-family, and the sonnet alias was honoured
        "anthropic": (lambda served: all(m.startswith("claude-") for m in served)
                      and any("sonnet" in m for m in served)),
        # nothing outside the provider's own catalogue may have served, AND the
        # alias must be honoured: a CLI that ignored the sonnet alias and served
        # the provider default (`glm-5.3`) would still be glm-prefixed, so the
        # honouring half is what makes a silent alias regression visible
        "glm": (lambda served: all(m.startswith("glm-") for m in served)
                and any("flash" in m for m in served)),
    }
    aliases = {"claude": "anthropic"}
    wanted = [aliases.get(a, a) for a in (argv or ["anthropic", "glm"])]
    unknown = [w for w in wanted if w not in cases]
    if unknown:
        print(f"unknown provider(s): {', '.join(unknown)}. "
              f"Known: {', '.join(sorted(cases))} (claude = anthropic)")
        return 2
    results = {name: probe(name, cases[name]) for name in wanted}
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
