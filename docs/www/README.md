# setcode.dev — Landing Page

Landing page for [setcode.dev](https://setcode.dev). Single `index.html` with images, zero build dependencies.

## Deploy

Hosted on **Cloudflare Pages**. Deploy from this directory:

```bash
cd docs/www
npx wrangler pages deploy .
```

- **Domain:** `setcode.dev` — Cloudflare Registrar + Cloudflare Pages
- **HTTPS:** automatic via Cloudflare
- **Preview URL:** `setcode-www.pages.dev`

Previously hosted on GitHub Pages (`gh-pages` branch). Migrated to Cloudflare Pages on 2026-03-31 (GitHub Actions minutes exhausted).

## Structure

```
docs/www/
├── index.html         ← single HTML file, the entire site
├── faq.html           ← frequently asked questions
├── favicon.svg
├── CNAME              ← legacy (GitHub Pages), not used by CF Pages
├── images/            ← screenshots, GIF, og-preview
├── worker/            ← Cloudflare Worker (contact form backend)
│   ├── src/index.js
│   └── wrangler.toml
├── .github/workflows/ ← GitHub Pages deploy (legacy)
└── .gitlab-ci.yml     ← GitLab Pages deploy (legacy)
```

## Contact Form Worker

The `worker/` directory contains a Cloudflare Worker that handles the contact form submission. It stores contacts in KV and sends notification emails.

Deploy separately:

```bash
cd docs/www/worker
npx wrangler deploy
```

The API token is stored locally (`~/.wrangler/` or env var), not in this repo.

## Redesign Plan — Pillars Framework (v2)

The current site has 12 capability cards in a flat grid. The redesign organizes them under 5 pillars that give the capabilities narrative structure.

### Principle

The pillars are the "why." The capabilities are the "how." Both stay.

```
Current:   [12 capabilities, flat grid]     → "it does a lot"
New:       [5 pillars, 12+6 capabilities]   → "5 principles, here's the proof"
```

### Page Structure

```
1. HERO (brownfield tagline added)
2. FIVE PILLARS (new — the spine of the page)
   ├── Each pillar has 2-4 capability cards (existing 12 + 6 new)
   ├── Each capability keeps its current technical depth
   └── + pillar-level tagline and "why"
3. PIPELINE carousel (unchanged + pillar badges)
4. WORKS EVERYWHERE (new — greenfield/brownfield/unit)
5. PROOF (consolidated — stats + reproducibility + self-healing + GIF)
6. COMMANDS (unchanged)
7. ECOSYSTEM (unchanged)
8. WHY NOW (unchanged)
9. WORK WITH US (unchanged)
10. EASTER EGG (unchanged)
```

### The Five Pillars

#### SPECIFY — Structured input, not prompts

> "Output quality depends on input quality. 90% of agent failures are underspecification."

Capabilities: `openspec_workflow`, `design_bridge`, `spec_flexibility` (new)

#### DECOMPOSE — Intelligent planning, not guessing

> "One big task fails. Many small ones succeed. Max 6 requirements per change — above that, failure rate spikes."

Capabilities: `dependency_dag` (new), `complexity_aware_allocation` (new), `parallel_worktrees`

#### SUPERVISE — Three-tier supervision, not babysitting

> "80% of the system is error handling. The happy path is trivial — anyone can do that."

Capabilities: `sentinel_supervisor`, `watchdog_intelligence` (new), `team_sync`

#### VERIFY — Deterministic quality, not vibes

> "Exit codes, not LLM judgment. You can't talk your way past a failing test."

Capabilities: `quality_gates[7]`, `self_healing`, `deterministic_output`, `spec_coverage` (new)

#### LEARN — Every run improves the next

> "The real value shows from run #2 onward. Every error occurs only once."

Capabilities: `cross_run_learnings`, `persistent_memory`, `template_system` (new)

### Capability Map

| Existing capability | Pillar | Change |
|---|---|---|
| parallel_worktrees | DECOMPOSE | text expanded |
| quality_gates[7] | VERIFY | unchanged |
| deterministic_output | VERIFY | unchanged |
| openspec_workflow | SPECIFY | unchanged |
| self_healing | VERIFY | unchanged |
| plugin_system | Ecosystem section | stays where it is |
| cross_run_learnings | LEARN | unchanged |
| design_bridge | SPECIFY | unchanged |
| web_dashboard | Ecosystem section | stays where it is |
| persistent_memory | LEARN | expanded (0 voluntary saves story) |
| sentinel_supervisor | SUPERVISE | expanded (3-tier model) |
| team_sync | SUPERVISE | unchanged |

6 new capabilities: `spec_flexibility`, `dependency_dag`, `complexity_aware_allocation`, `watchdog_intelligence`, `spec_coverage`, `template_system`.

**Total: 18 capabilities** (12 existing + 6 new) organized under 5 pillars.

### What a CTO Remembers After 5 Minutes

1. "5 pillars: SPECIFY, DECOMPOSE, SUPERVISE, VERIFY, LEARN"
2. "Works on brownfield too, not just greenfield"
3. "Exit codes, not LLM judgment"
4. "Every run improves the next"
5. "83-87% reproducibility across 30+ E2E runs"
