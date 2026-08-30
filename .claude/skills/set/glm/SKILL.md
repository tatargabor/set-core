---
name: glm
description: Run Claude Code against the z.ai GLM models with the measured, working parameters — one-shot `-p` calls, batch loops, or an interactive session. Use when the user asks to run something on GLM, on a non-Anthropic model, or to compare models on the same task (an A/B run), and when a GLM run behaves strangely — silent stalls, "Prompt is too long", or a 400 on the model name. Carries the three failure modes measured in production so they do not have to be rediscovered.
---

# Running GLM — `set-glm`

**The hard part is not switching the model — it is the context window.** The Claude Code CLI
does not know GLM's window, so it cuts to a conservative value (~200k) — and a long prompt
either fails loudly or runs in a silent compact loop. This skill exists so that nobody has
to measure that again.

⚠ **Switching is always a USER decision.** No automatics and no silent fallback: on missing
config the runner stops, it does not fall back to Claude. A silent fallback is the worst
outcome because the run would still finish — just inside the other framework, with nothing
telling you which one.

## Usage

```bash
set-glm --check                     # config + LIVE probe call — start here
set-glm -p "prompt"                 # one-shot call
set-glm -p "…" --output-format json # structured output (with token- and cost-fields)
set-glm                             # interactive session on GLM
set-glm --print-env                 # what it sets (token masked)
```

Every other flag passes through to `claude` unchanged (`--allowedTools`,
`--json-schema`, `--append-system-prompt`, …). `--model` and `--autocompact` are only
added when the caller did not supply them.

### Configuration — ONE central file (since 2026-08-29)

**`~/.config/set-core/providers.json`**, mode `0600`. This is the only place the framework
reads a provider credential from; `set-glm` and the fleet's agent-owner call the same
resolver, so the measured launch parameters live in one place and do not drift apart.

```bash
set-providers path        # where it is expected
set-providers show        # what is in it — token masked
set-providers migrate     # carry the old glm.env over, ONE command
```

Precedence has three levels: **machine-level default → project override → the request
itself**. The model is decided per field; the **credential and its endpoint are ONE block** —
a level either provides both or is rejected. A key is issued for one endpoint, and taking the
two from different levels is a combination nobody has described: best case a 401, worst case
the other bill.

#### The old `glm.env` — one release of grace, then gone

| what it was | what became of it |
|---|---|
| `./.env` in the repo (`GLM_*` lines) | **DISCONTINUED, no longer read** — the error says it was discontinued, not merely that no credential was found |
| `~/.config/set-core/glm.env` | **still works for one release**, with a warning on every resolution |

The warning names the old file, the new one, and the command. `migrate` is **explicit**,
never a side effect of a read: a read writes nothing, and even the migration leaves
`glm.env` in place. An existing `providers.json` is not overwritten silently.

Only the `GLM_`-prefixed lines are read from the old file — deliberately. A `source .env`
would also pull in `ANTHROPIC_API_KEY` — exactly the key that would silently redirect the
call to the platform bill.

## The measured parameters (2026-08-29) — do not re-measure

| what | value | env |
|---|---|---|
| endpoint | `https://api.z.ai/api/anthropic` | `GLM_BASE_URL` |
| model | `glm-5.3-flash` — **no prefix** | `GLM_MODEL` |
| context window | **900000** (`CLAUDE_CODE_MAX_CONTEXT_TOKENS`) | `GLM_CONTEXT_TOKENS` |
| auto-compact | **700k** | `GLM_AUTOCOMPACT` |

Measured capabilities: **800,016 input tokens accepted** (`model_context_window_exceeded` at
1.05M, so the window is ~1M) · max output **≥131,072** · the **prompt cache works** without
`cache_control` (2nd identical call: `input=16`, `cache_read=120,000`) · `--json-schema`,
`--allowedTools` and the Write/Edit tool all work. Returns 200 for: `glm-4.6`, `glm-5.3`,
`glm-5.3-flash`, `glm-4.5`, `glm-4.5-air`.

## Three traps — each one a MEASURED failure

1. ⚠ **The model name must not carry a gateway prefix.** A `zai/glm-5.3-flash`-shaped name
   gets `[1214][modelCode: does not exist]` 400 back — that is the OpenRouter/LiteLLM
   format. The runner therefore rejects a name containing `/` BEFORE starting: otherwise a
   night loop fails on its first call.

2. ⚠⚠ **`--autocompact` alone is not enough.** The CLI clips the threshold to the window it
   assumes for an unknown model. The same ~250k-token prompt, four variants:

   | setting | result |
   |---|---|
   | only `--autocompact 700k` | `Prompt is too long`, input=0 |
   | `MAX_CONTEXT_TOKENS` + `DISABLE_…_ENFORCEMENT` | OK, `input_tokens=524,731` |
   | **only `CLAUDE_CODE_MAX_CONTEXT_TOKENS`** | **OK — necessary AND sufficient** |
   | only `…_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT` | `Prompt is too long` |

   The second env var is therefore NOT set: the redundant env only hides which one works.

   **A compact is NOT an error message — from the outside it looks like a "slow model".**
   The measured failure: compact at 180,174 tokens (227 s), again half a minute later,
   finally the CLI's own message — *"Autocompact is thrashing: the context refilled to the
   limit within 3 turns of the previous compact, 3 times in a row"* — **9.5 minutes, zero
   lines written**. If a GLM run is suspiciously silent for a long time, look for
   **`compact_boundary`** and `status: compacting` events in the `--output-format
   stream-json` log; nothing among the tool events shows it.

3. ⚠ **A `.env` is often git-tracked.** In a worktree, a `git reset --hard` takes the
   `GLM_*` lines with it, and the run stops with "GLM_TOKEN is missing". This is one reason
   the in-repo `.env` tier was **discontinued**: the credential's home is the machine-level
   `~/.config/set-core/providers.json`, and one repo's cleanup must not take the others'
   with it.

## Subagents on GLM — the provider comes from the PARENT, not the agent definition

Measured 2026-08-29, three attempts. **A subagent inherits the parent session's ENDPOINT**
(the `spawn` carries the parent's env forward); the agent definition's `model:` field only
chooses within that endpoint.

| parent | the agent's `model:` field | what happens |
|---|---|---|
| Anthropic | `glm-5.3-flash` | ⛔ **`model_not_found` (HTTP 404)** — the subagent starts, then falls over |
| GLM (z.ai env) | `glm-5.3-flash` | ✅ works, `modelUsage` = `glm-5.3-flash` only |
| GLM (z.ai env) | `sonnet` | ⚠ **runs**, but the call goes to **z.ai** and is billed as `claude-sonnet-5` |

**The recipe is therefore: start the PARENT on GLM.** There is no way to switch provider
per agent — `set-glm` is the parent session, and its subagents carry it with them.

⚠ **The third row is the trap, and it must be said out loud.** Under a GLM parent, a
`model: sonnet` agent does not fall over — z.ai accepts the name — and the `modelUsage`
shows **two rows**: `glm-5.3-flash` (`costBasis: unknown`) and `claude-sonnet-5`
(`costBasis: list`, `ctx=200000`). So the screen shows an Anthropic model name while the
bill is z.ai's, and the env holds no Anthropic auth at all. This is the *"other bill, same
look"* defect class — the same one the ledger's provider field closes from the other side.


**And it is not relabelling: REAL Claude comes back.** Measured — asked "which model family
are you?" through the z.ai endpoint with `--model sonnet`, the answer was **"Claude"**; the
same question with `glm-5.3-flash` answered **"GLM"**; on the Anthropic endpoint with
sonnet, **"Claude"** again. So z.ai **forwards** the Claude call — onto its own bill. (A
model's self-report alone is not proof, but the GLM control self-reports as GLM, so the
signal is worth something.)

This sharpens what the real risk is: **you do not get something other than what you asked
for — you get exactly that, on a different bill**, and nothing signals it. A `model:
sonnet` agent under a GLM parent is therefore not "lower quality" — it is **invisibly
billed elsewhere**.

**Therefore:** if you want an agent definition to run under a GLM parent, either **leave
out the `model:` field** (it inherits the parent's model, and there is nothing to
misread) or write a **GLM model** into it. A `model: sonnet` under a GLM parent is
misleading: it promises what it does not deliver.

### Which GLM model for review — measured on five cases

Five code-review cases (counter-race · VAT rounding · date-UTC · cron idempotency · one
**deliberately clean** file to measure the false-positive rate):

| model | hits | avg time | avg output |
|---|---|---|---|
| `glm-5.3-flash` | **5/5** | 12.7 s | 222 tokens |
| `sonnet` (for comparison) | **5/5** | 5.4 s | 74 tokens |
| `glm-4.6` | 2/2 (short trial) | 15.7 s | 604 tokens |
| `glm-4.5-air` | ⛔ **0/2** | 11.0 s | 878 tokens |

**`glm-4.5-air` is excluded**: twice, on two different defect classes, it missed — once it
said "NO BUG" on a real one — and burned 8× more tokens than flash to do it. For a
review agent that is the worst outcome: silence sounds reassuring.

**`glm-5.3-flash` is suitable** — it also said "NO BUG" correctly on the clean file (it
does not manufacture false positives). In exchange it is 2.4× slower and 3× more verbose
than sonnet.

⚠ The sample was **easy**: five self-contained, 5–8-line, textbook defects. A real review
is harder — a large file, project context, rules in tension — and this measurement says
nothing about that.

## What the cost field LIES about

The `--output-format json` `total_cost_usd` field computes with **Anthropic pricing**, so
for a GLM run it is not a real bill. For comparing two models, **wall-clock** and the
**token counts** are the honest measures, dollars are not — and if you write it into a
ledger, state next to it that it is price-equivalent.

## If you run a loop with it (A/B, night loop)

- **Same prompt, same task** — otherwise it is not a measurement, it is an anecdote.
- **The gate line is part of the measurement.** The measured GLM run's work was good, but a
  lint gate rejected the commit because the model tried to silence a rule with a
  **non-existent** ignore directive instead of the repo's own precedent. Only the gate
  caught it — the test was green. Whoever compares models counts the commits that **went
  through the gate**, not the lines written.
- **Log events, not just output** (`--output-format stream-json`): otherwise the compact
  is invisible, and you will blame the model for the slowdown.

## Related

- `bin/set-glm` — the runner; the measured rationale is in the file header, in comments
- `bin/claude-local` — the same for a local Ollama model (the sibling case)
