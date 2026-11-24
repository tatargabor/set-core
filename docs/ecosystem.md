# The repository family

set-core is one repository in a family. This page lists every **public** repository of that
family, says in one line what it is, and states how it relates to set-core. A relation is written
here only where it was measured; where it was not, the page says so instead of guessing.

Measured 2026-11-24 (`gh repo list <owner> --json name,visibility,description`).

## The `set-*` tools — owner `tatargabor`

| repository | what it is | relation to set-core |
|---|---|---|
| [set-core](https://github.com/tatargabor/set-core) | the harness and fleet layer around Claude Code: fleet dashboard and agent owner, relay hooks, project deploy, leak scan, machine doctor, knowledge search | this repository |
| [set-agent-comm](https://github.com/tatargabor/set-agent-comm) | messaging between agent sessions on one machine — a file channel with a registry, rooms and typed messages, over MCP and a CLI (`sac`) | **runtime dependency** — the bus every set-core session talks over; set-core deploys its hooks into projects |
| [set-claude-handoff](https://github.com/tatargabor/set-claude-handoff) | session handoff: one thread's open work and measured state written to an ID-tagged file, so a `/clear` beats a compact; the auto-clear cycle | **companion** — set-core's deploy installs its reload and arm hooks (`--auto-clear`) |
| [set-copilot](https://github.com/tatargabor/set-copilot) | voice dictation and a real-time meeting copilot for Claude Code, cross-referenced against the project knowledge base | **companion** — used from set-core sessions (`/ds`, `/dd`); set-core carries its OpenSpec adapter |
| [set-atlas](https://github.com/tatargabor/set-atlas) | a generated, compact map of a running app's UI — screens, menus, actions — for agents that need the surface before designing on it | standalone tool of the same family |
| [set-demo](https://github.com/tatargabor/set-demo) | feature demos recorded from a real web app: one scenario YAML → an MP4 and a self-contained HTML page | standalone tool of the same family |
| [set-voice-agent-delivery](https://github.com/tatargabor/set-voice-agent-delivery) | an AI voice agent for outbound customer calls; ships a set-core project type | **plugin** of the orchestration-era profile layer — its future follows `profile-layer-decision` |

## AI+ — org `itlinekft`

AI+ is a product family by ITLine Kft. built in the same agent fleet that set-core runs. Its
public repositories:

| repository | what it is | relation to set-core |
|---|---|---|
| [aiplus-office](https://github.com/itlinekft/aiplus-office) | a free AI+ module: Claude makes Word, Excel, PowerPoint and PDF files with free office apps | **developed with set-core** — registered, deployed, and using its knowledge base, wave board, handoff, issue register and leak-scan gates |
| [aiplus-desktape](https://github.com/itlinekft/aiplus-desktape) | control desktop programs that have no API: an agent's clicks kept as a YAML tape, replayed and checked step by step with zero model tokens; the same tape runs as a test or a captioned video | developed in the fleet; its sessions appear on the fleet dashboard |
| [aiplus-pilota](https://github.com/itlinekft/aiplus-pilota) | profiles that let Claude operate existing desktop programs through their own UI, driven by desktape | AI+ family; relation to set-core not measured |
| [aiplus-plugins](https://github.com/itlinekft/aiplus-plugins) | the Claude plugin marketplace of the AI+ products | AI+ family; relation to set-core not measured |
| [genoffice](https://github.com/itlinekft/genoffice) | an open-source AI office suite — document, spreadsheet, slide, PDF, Markdown and HTML editors with a built-in agent, plus a CLI and agent skill for creating real `.docx`/`.xlsx`/`.pptx` files locally | AI+ family; relation to set-core not measured |
| [wordcraft](https://github.com/itlinekft/wordcraft) | an open-source, clean-room reimplementation of a word processor in pure Rust | AI+ family; relation to set-core not measured |
| [aiplus-studio-meres](https://github.com/itlinekft/aiplus-studio-meres) | **temporary** — a measurement marketplace with an invented test plugin; its own description says it will be removed | AI+ family; listed here only, not in the README |

"Relation not measured" means only the one machine this page was written on was checked: these
repositories have no set-core registration and no recorded sessions there. The fleet also runs on
a second machine, which was not measured.

## What a relation means

- **runtime dependency** — set-core does not do its job without it.
- **companion** — a separate tool set-core installs, deploys hooks for, or calls; set-core works
  without it.
- **developed with set-core** — the project is registered with `set-project`, set-core's rules,
  hooks and gates are deployed into it, and its development runs through the fleet.
- **plugin** — implements one of set-core's extension points.
