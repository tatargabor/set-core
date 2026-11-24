# set-core

**A harness for running many Claude Code sessions across many projects** — see them all on one
screen, answer them from anywhere, keep them from publishing what they must not, carry their
state across a context reset, and let them talk to each other.

[![Release: v2.0.0](https://img.shields.io/badge/Release-v2.0.0-blue.svg)](docs/release/v2.0.0.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux & macOS (Apple Silicon)](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20(Apple%20Silicon)-lightgrey.svg)]()
[![Website](https://img.shields.io/badge/Website-setcode.dev-22c55e)](https://setcode.dev)

---

## What it is

set-core is the fleet and tooling layer around Claude Code that I use every day across a few
dozen projects. It started as an orchestration engine — spec in, parallel agents, gates, merged
features out. That engine works and is documented, but the daily work turned out to need
something else: one person supervising a dozen hand-driven sessions at once. **v2.0.0 is the
release that says so.** Why, and what was learned on the way:
[From orchestration to harness](docs/learn/from-orchestration-to-harness.md).

| part | what it does |
|---|---|
| **fleet dashboard + agent owner** (`set-web`, `set-agent-owner`) | launch, watch, instruct and stop agent sessions across projects from one screen; idle sessions are closed by a timer |
| **relay hooks + auto-answer** | a session's questions, permission prompts and notifications reach the dashboard or a phone instead of sitting in a terminal nobody looks at; a decider can propose answers from the session's own sources — never an outward step, never a permission |
| **`set-project`** | deploys rules, skills, hooks and the MCP registration into a project — provenance-guarded, so a file the project edited is never overwritten, and retired files are removed only when untouched |
| **project role rules** (`set-project roles`) | a generated, git-excluded rule in every project naming its role and relations; a public repository names only public siblings |
| **`set-kb`** | knowledge-base search over a project's documents, as a CLI and an MCP tool |
| **`set-leakscan`** | commit, push and agent-tool gates that refuse to publish client names, credentials, local paths and private deny-list terms |
| **`set-doctor`** | the machine check — install, checkout, tools, every registered project — each finding with the command that fixes it |
| **`set-watchdog`** | probes the fleet for quiet failures through the day and hands real ones to the project that owns them |
| **providers** (`set-providers`, `set-glm`) | run the same sessions on a non-Anthropic model, explicitly, never as a silent fallback |
| **`set-wave-board`** | a progress board a project publishes for the people it works with |
| **OpenSpec** | every framework change goes through proposal → specs → design → tasks → verify |

> **The orchestration engine is dormant in v2.0.0.** Its `/set:*` commands are no longer deployed
> into projects, and the engine, its CLI and its web pages are being removed in stages — see the
> [roadmap](docs/roadmap.md). What it did, its benchmarks and its lessons are kept as
> [a record](docs/learn/orchestration-pipeline.md).

---

## Install

```bash
git clone https://github.com/tatargabor/set-core.git
cd set-core && ./install.sh
```

This links every `set-*` CLI into `~/.local/bin` and starts the dashboard as a user service
(systemd on Linux, launchd on macOS). Open http://localhost:7400 — you should see the fleet.

```bash
set-doctor                          # the machine check; each finding names its fix
cd ~/my-project
set-project init --dry-run          # read the plan: what it would write, and what it never touches
set-project init                    # deploy rules, skills, hooks and the MCP registration
```

The full setup — the agent bus, session handoff, the question relay and the auto-answer — with
a check for every step: [bringing a machine up to the fleet](docs/guide/fleet-machine-setup.md).

**Optional — a non-Anthropic model.** Declare a provider once in
`~/.config/set-core/providers.json` (mode `0600`); `set-providers list` shows the catalogue and
`set-providers show --provider <name>` the resolved launch, without printing a credential.
Switching is always explicit — an absent configuration stops loudly. Details:
[provider configuration](docs/reference/configuration.md#provider-configuration-providersjson).

---

## The repository family

| repository | what it is |
|---|---|
| **[set-core](https://github.com/tatargabor/set-core)** | this repository — the harness and fleet layer |
| [set-agent-comm](https://github.com/tatargabor/set-agent-comm) | the agent bus: messaging between sessions on one machine (`sac`) — set-core's runtime dependency |
| [set-claude-handoff](https://github.com/tatargabor/set-claude-handoff) | session handoff and the auto-clear cycle, so a `/clear` beats a compact |
| [set-copilot](https://github.com/tatargabor/set-copilot) | voice dictation and a real-time meeting copilot for Claude Code |
| [set-atlas](https://github.com/tatargabor/set-atlas) | a generated, compact map of a running app's UI, for agents |
| [set-demo](https://github.com/tatargabor/set-demo) | feature demos recorded from a real web app: scenario YAML → MP4 + HTML |
| [set-voice-agent-delivery](https://github.com/tatargabor/set-voice-agent-delivery) | an AI voice agent for outbound calls; a set-core project-type plugin |

**Built in the same fleet — the AI+ products of ITLine** (org `itlinekft`):

| repository | what it is |
|---|---|
| [aiplus-office](https://github.com/itlinekft/aiplus-office) | free AI+ module: Claude makes Word, Excel, PowerPoint and PDF files with free office apps |
| [aiplus-desktape](https://github.com/itlinekft/aiplus-desktape) | control desktop programs that have no API — an agent's clicks as a YAML tape, replayed and checked with zero model tokens |
| [aiplus-pilota](https://github.com/itlinekft/aiplus-pilota) | profiles that let Claude operate existing desktop programs through their own UI, driven by desktape |
| [aiplus-plugins](https://github.com/itlinekft/aiplus-plugins) | the Claude plugin marketplace of the AI+ products |
| [genoffice](https://github.com/itlinekft/genoffice) | an open-source AI office suite with a built-in agent, plus a CLI and skill for real `.docx`/`.xlsx`/`.pptx` files |
| [wordcraft](https://github.com/itlinekft/wordcraft) | an open-source, clean-room word processor in pure Rust |

How each one relates to set-core — measured, not assumed — is in
[the repository family](docs/ecosystem.md).

---

## Documentation

| section | contents |
|---|---|
| **[From orchestration to harness](docs/learn/from-orchestration-to-harness.md)** | why set-core changed direction, what it is now, what was removed |
| **[Guide](docs/guide/)** | machine setup, the dashboard, OpenSpec |
| **[Reference](docs/reference/)** | CLI tools, configuration, architecture, plugins |
| **[Learn](docs/learn/)** | the development journey, lessons learned, the orchestration record |
| **[Roadmap](docs/roadmap.md)** | the retirement stages and what comes next |
| **[Release notes](docs/release/)** | per release |
| **[Contributing](CONTRIBUTING.md)** | dev setup, testing, plugin development, code style |

---

## License

MIT — See [LICENSE](LICENSE) for details.

**Third-party notices.** The knowledge-base search engine (`lib/set_kb/`) is a
port of MIT-licensed upstream code; its copyright and permission notice, the
upstream commit it derives from and the port lineage are in
[`lib/set_kb/LICENSE-UPSTREAM`](lib/set_kb/LICENSE-UPSTREAM).

**Website:** [setcode.dev](https://setcode.dev) · **Source:** [git.setcode.dev/root/set-core](https://git.setcode.dev/root/set-core)
