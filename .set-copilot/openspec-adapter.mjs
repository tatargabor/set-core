/**
 * set-copilot knowledge adapter for an OpenSpec-shaped project.
 *
 * The built-in `markdown` adapter derives topics from page titles and `##`
 * headings. In an OpenSpec repo that yields the wrong things: every spec.md is
 * titled "<slug> Specification" and its only `##` headings are "Purpose" and
 * "Requirements". The routing keys a meeting actually uses are the CAPABILITY
 * names — and people speak them ("loop idle detection"), not as slugs.
 *
 * So this adapter indexes the repo the way OpenSpec structures it:
 *
 *   capabilities   openspec/specs/<slug>/spec.md   → what the system DOES (current truth)
 *   active changes openspec/changes/<slug>/        → what is IN FLIGHT (not yet truth)
 *   rules          .claude/rules/*.md              → binding conventions
 *   guides         docs/guide, docs/reference      → how it is used
 *
 * The archive (openspec/changes/archive/, 2200+ files) is deliberately NOT
 * indexed: archived changes describe superseded intent and would contradict the
 * specs. It stays greppable on demand during the meeting.
 */

import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join, basename, dirname } from "node:path";
import { execSync } from "node:child_process";

const SPECS_DIR = "openspec/specs";
const CHANGES_DIR = "openspec/changes";
const RULES_DIR = ".claude/rules";
const DOC_DIRS = ["docs/guide", "docs/reference"];

/**
 * The research corpus: point-in-time investigations, benchmark rounds, run findings.
 *
 * These are NOT specs — they are what we MEASURED and CONCLUDED, on a given day. Their
 * defining property is that they go stale: docs/research/README.md says it outright
 * ("the conclusions may be partially or fully superseded by later work"). A copilot that
 * quotes a March benchmark as current fact is worse than one that says nothing.
 *
 * So the index carries, for every research doc: its DATE, its headline findings, its
 * FAMILY (successive rounds of the same investigation — benchmark v3…v6), and the other
 * research docs it references. That is enough for the copilot to place a claim in time
 * and to know which later document might have overturned it. The full text stays on disk
 * and is grepped on demand — 300 kB of measurements does not belong in a preload.
 */
const RESEARCH_GLOBS = [
  { dir: "docs/research", skip: /^README\.md$/ },
  { dir: "benchmark", keep: /^(v\d+-results|.*-results)\.md$/ },
  { dir: "local-docs", keep: /(findings|results)/i },
  { dir: "docs/archive", keep: /^(research|benchmark)-/ },
];

/** Section headings whose content IS the conclusion of a research doc. */
const CONCLUSION_HEADINGS =
  /^#{2,3}\s+(executive summary|conclusions?|tl;?dr|overall|key findings?|findings?|results?|verdict|recommendations?|top \d+ improvement recommendations?|summary)\s*$/i;

/** Slug → a stem that matches both "loop-idle-detection" and "loop idle detection". */
function stemFromSlug(slug) {
  const words = slug.split(/[-_]/).filter(Boolean);
  if (!words.length) return null;
  const escaped = words.map((w) => w.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return escaped.join("[- _]?");
}

function dirsIn(root, rel) {
  const abs = join(root, rel);
  if (!existsSync(abs)) return [];
  return readdirSync(abs, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name !== "archive" && !e.name.startsWith("."))
    .map((e) => e.name)
    .sort();
}

function read(root, rel) {
  const abs = join(root, rel);
  try {
    return statSync(abs).isFile() ? readFileSync(abs, "utf-8") : "";
  } catch {
    return "";
  }
}

/** The paragraph under a given `##` section, collapsed to one line. */
function section(body, name) {
  const re = new RegExp(`^##\\s+${name}\\s*$([\\s\\S]*?)(?=^##\\s|\\Z)`, "im");
  const m = body.match(re);
  if (!m) return "";
  return m[1].trim().split(/\n\s*\n/)[0]?.replace(/\s+/g, " ").trim() ?? "";
}

/** Bullet lines under a `##` section. */
function bullets(body, name, limit = 6) {
  const re = new RegExp(`^##\\s+${name}\\s*$([\\s\\S]*?)(?=^##\\s|\\Z)`, "im");
  const m = body.match(re);
  if (!m) return [];
  return m[1]
    .split("\n")
    .filter((l) => /^\s*[-*]\s+/.test(l))
    .map((l) => l.replace(/^\s*[-*]\s+/, "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .slice(0, limit);
}

function firstHeading(raw) {
  return raw.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? "";
}

/** Body with heading lines removed — used to find the opening paragraph of a doc. */
function stripHeadings(raw) {
  return raw
    .split("\n")
    .filter((l) => !/^#{1,6}\s/.test(l))
    .join("\n");
}

function clip(s, n) {
  return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
}

class OpenSpecAdapter {
  name = "openspec";

  constructor(ctx) {
    this.ctx = ctx;
    this.root = ctx.projectRoot;
  }

  // ---- capabilities (current truth) ---------------------------------------

  capabilities() {
    if (this._caps) return this._caps;
    this._caps = dirsIn(this.root, SPECS_DIR).map((slug) => {
      const raw = read(this.root, join(SPECS_DIR, slug, "spec.md"));
      const purpose = section(raw, "Purpose");
      const reqs = [...raw.matchAll(/^###\s+Requirement:\s*(.+)$/gim)].map((m) => m[1].trim());
      // 306 of 431 spec.md files carry a placeholder Purpose ("TBD — restored after
      // delta-sync structural cleanup"), left behind by the archive/delta-sync pass.
      // The requirement titles are the real content, so they become the one-liner.
      const usable = purpose && !/^TBD\b/i.test(purpose) ? purpose : "";
      return {
        slug,
        purpose: usable,
        headline: usable || reqs.slice(0, 2).join(" · ") || "(no purpose, no requirements)",
        purposeIsPlaceholder: !usable,
        requirements: reqs,
      };
    });
    return this._caps;
  }

  // ---- active changes (in flight, NOT truth yet) ---------------------------

  activeChanges() {
    if (this._changes) return this._changes;
    this._changes = dirsIn(this.root, CHANGES_DIR).map((slug) => {
      const proposal = read(this.root, join(CHANGES_DIR, slug, "proposal.md"));
      const tasks = read(this.root, join(CHANGES_DIR, slug, "tasks.md"));
      const done = (tasks.match(/^\s*-\s*\[x\]/gim) || []).length;
      const open = (tasks.match(/^\s*-\s*\[ \]/gim) || []).length;
      return {
        slug,
        why: clip(section(proposal, "Why"), 200),
        what: bullets(proposal, "What Changes", 5).map((b) => clip(b, 160)),
        progress: done + open > 0 ? `${done}/${done + open} tasks` : "no tasks.md",
      };
    });
    return this._changes;
  }

  // ---- research corpus (measured, dated, and perishable) -------------------

  researchFiles() {
    const out = [];
    for (const g of RESEARCH_GLOBS) {
      const abs = join(this.root, g.dir);
      if (!existsSync(abs)) continue;
      for (const f of readdirSync(abs)) {
        if (!f.endsWith(".md")) continue;
        if (g.skip && g.skip.test(f)) continue;
        if (g.keep && !g.keep.test(f)) continue;
        out.push(`${g.dir}/${f}`);
      }
    }
    return out;
  }

  /**
   * A date for every research doc, best source first: the filename, an explicit
   * `**Date**:` line, frontmatter, then the commit that introduced the file. Undated
   * research is the dangerous kind — the copilot cannot tell whether it still holds —
   * so we always produce something rather than leaving the field blank.
   */
  dateOf(rel, raw) {
    const fromName = rel.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (fromName) return fromName[0];
    const fromBody = raw.match(/^\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})/im) || raw.match(/^date:\s*(\d{4}-\d{2}-\d{2})/im);
    if (fromBody) return fromBody[1];
    try {
      const d = execSync(
        `git -C "${this.root}" log --diff-filter=A --format=%ad --date=short -1 -- "${rel}"`,
        { encoding: "utf-8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"] },
      ).trim();
      if (d) return d;
    } catch {
      /* not in git, or git unavailable */
    }
    return "undated";
  }

  /**
   * Successive rounds of the same investigation. "benchmark/v3-results.md" …
   * "v6-results.md" are one family, and v6 is the one that still counts. Without this
   * the copilot has no way to know that a v3 number was re-measured three times since.
   */
  familyOf(rel) {
    const base = basename(rel, ".md");
    // The successive benchmark rounds. Scoped to the directory on purpose: an unrelated
    // `docs/research/benchmark-results.md` (memory benchmarks) shares the name but not
    // the investigation, and lumping them together marked the current v6 as superseded.
    if (/^v\d+-results$/.test(base)) return "benchmark/craftbazaar-rounds";
    const stem = base
      .replace(/-\d{4}-\d{2}-\d{2}$/, "")
      .replace(/-run-?\d+.*$/i, "")
      .replace(/-\d{8}-\d{4}.*$/, "");
    return `${dirname(rel)}/${stem}`;
  }

  /**
   * The bullets/lines under the doc's conclusion heading — what it actually concluded.
   * Falls back to the opening paragraph, because a doc whose headings we do not
   * recognise would otherwise appear in the index as a title with nothing under it —
   * which reads as "we investigated this and concluded nothing".
   */
  conclusions(raw, limit = 5) {
    const usable = (t) => {
      const bullet = t.replace(/^\s*(?:[-*]|\d+\.)\s+/, "").trim();
      if (bullet.length < 25) return null;
      if (bullet.startsWith("|") || bullet.startsWith("```")) return null;
      // Box-drawing art (the shodh audit is full of it) reads as prose to a letter-ratio
      // check — the cells contain real words. Reject on the box characters themselves.
      if (/[│┌└├─┐┘┤┬┴┼╔╚║═]/.test(bullet)) return null;
      const letters = (bullet.match(/\p{L}/gu) || []).length;
      if (letters < bullet.length * 0.5) return null;
      if (bullet.split(/\s+/).length < 5) return null;
      return clip(bullet.replace(/\s+/g, " "), 190);
    };

    const out = [];
    let inside = false;
    for (const line of raw.split("\n")) {
      if (/^#{1,3}\s/.test(line)) {
        inside = CONCLUSION_HEADINGS.test(line);
        continue;
      }
      if (!inside) continue;
      const u = usable(line.trim());
      if (!u) continue;
      out.push(u);
      if (out.length >= limit) break;
    }
    if (out.length) return out;

    // Fallback: the first real paragraph after the title.
    for (const block of stripHeadings(raw).split(/\n\s*\n/)) {
      const u = usable(block.trim());
      if (u) return [u];
    }
    return [];
  }

  /** Which other research docs this one cites — the "builds on / overturns" skeleton. */
  crossRefs(raw, allBasenames) {
    const hits = new Set();
    for (const b of allBasenames) {
      if (raw.includes(b)) hits.add(b);
    }
    return [...hits];
  }

  research() {
    if (this._research) return this._research;
    const files = this.researchFiles();
    const basenames = files.map((f) => basename(f));
    const docs = files.map((rel) => {
      const raw = read(this.root, rel);
      const family = this.familyOf(rel);
      return {
        file: rel,
        title: firstHeading(raw) || basename(rel, ".md"),
        date: this.dateOf(rel, raw),
        family,
        /** The spoken form: "craftbazaar-rounds", "pi-mono-comparison". */
        familyName: family.split("/").pop(),
        conclusions: this.conclusions(raw),
        refs: this.crossRefs(raw, basenames.filter((b) => b !== basename(rel))),
      };
    });
    // Chronological: the reader must be able to see what came after what.
    docs.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    // Newest member of each family is the one that still counts.
    const latest = new Map();
    for (const d of docs) latest.set(d.family, d.file);
    for (const d of docs) d.isLatestOfFamily = latest.get(d.family) === d.file;
    this._research = docs;
    return this._research;
  }

  rules() {
    const abs = join(this.root, RULES_DIR);
    if (!existsSync(abs)) return [];
    return readdirSync(abs)
      .filter((f) => f.endsWith(".md"))
      .sort()
      .map((f) => {
        const raw = read(this.root, join(RULES_DIR, f));
        return { file: `${RULES_DIR}/${f}`, title: firstHeading(raw) || basename(f, ".md") };
      });
  }

  guides() {
    const out = [];
    for (const dir of DOC_DIRS) {
      const abs = join(this.root, dir);
      if (!existsSync(abs)) continue;
      for (const f of readdirSync(abs).filter((n) => n.endsWith(".md")).sort()) {
        const raw = read(this.root, join(dir, f));
        const headings = [...raw.matchAll(/^##\s+(.+)$/gm)].map((m) => m[1].trim());
        if (!headings.length) continue;
        out.push({
          domain: firstHeading(raw) || basename(f, ".md"),
          file: `${dir}/${f}`,
          keyFacts: headings.slice(0, 8),
        });
      }
    }
    return out;
  }

  // ---- KnowledgeAdapter contract -------------------------------------------

  keywordPatterns() {
    const seeds = [...this.ctx.seedKeywords];
    const taken = new Set(seeds.map((s) => s.topic.toLowerCase()));
    const out = [...seeds];

    const add = (topic, slug) => {
      const key = topic.toLowerCase();
      if (taken.has(key)) return;
      const stem = stemFromSlug(slug);
      if (!stem) return;
      taken.add(key);
      out.push({ topic, stems: [stem] });
    };

    // Capabilities first — they are the current truth, so they win the label.
    for (const c of this.capabilities()) add(c.slug, c.slug);
    // Active changes, labelled so the copilot never mistakes intent for truth.
    for (const c of this.activeChanges()) add(`change:${c.slug}`, c.slug);
    // Research families. The family key is directory-qualified (to keep unrelated
    // same-named docs apart), but a person says "pi mono comparison", not
    // "docs/research/pi-mono-comparison" — so the STEM comes from the last segment only.
    for (const d of this.research()) add(`research:${d.familyName}`, d.familyName);

    return out;
  }

  enrichedContext() {
    return {
      generated: "generated",
      // "decisions" = the capability specs: what the system is SPECIFIED to do.
      decisions: this.capabilities().map((c) => ({
        id: c.slug,
        title: clip(c.headline, 160),
        summary: c.requirements.length
          ? `${c.requirements.length} req: ${clip(c.requirements.slice(0, 3).join(" | "), 220)}`
          : "no requirements section",
      })),
      deferred: this.readDeferred(),
      // "cards" = work in flight. NOT truth — proposed / partially built.
      cards: this.activeChanges().map((c) => ({
        name: `change:${c.slug}`,
        facts: [`[${c.progress}] ${c.why}`, ...c.what],
      })),
      domainFaq: [
        ...this.guides(),
        // Research goes into lite mode too — dated, so it can never be read as timeless.
        ...this.research().map((d) => ({
          domain: `${d.date} — ${d.title}${d.isLatestOfFamily ? " [CURRENT]" : " [SUPERSEDED?]"}`,
          file: d.file,
          keyFacts: d.conclusions,
        })),
      ],
      recentIncidents: this.recentFixes(),
    };
  }

  readDeferred() {
    const markers = (this.ctx.deferredMarkers || []).filter(Boolean);
    if (!markers.length) return [];
    const re = new RegExp(markers.join("|"), "iu");
    const out = [];
    const scan = (rel) => {
      const raw = read(this.root, rel);
      for (const line of raw.split("\n")) {
        if (!re.test(line)) continue;
        out.push({
          req: "",
          description: clip(line.replace(/^[-*\s>]+/, "").trim(), 180),
          source: rel,
        });
      }
    };
    for (const c of this.capabilities()) scan(join(SPECS_DIR, c.slug, "spec.md"));
    for (const c of this.activeChanges()) scan(join(CHANGES_DIR, c.slug, "proposal.md"));
    return out.slice(0, 60);
  }

  recentFixes() {
    try {
      const log = execSync(
        `git -C "${this.root}" log --since="30 days ago" --oneline --grep="fix"`,
        { encoding: "utf-8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"] },
      );
      return log.split("\n").filter(Boolean).slice(0, 30)
        .map((line) => ({ date: "", description: line, domain: "" }));
    } catch {
      return [];
    }
  }

  digestMarkdown() {
    const caps = this.capabilities();
    const changes = this.activeChanges();
    const L = [
      "# set-core knowledge digest",
      "",
      "**Authority order:** `openspec/specs/` = what the system IS (current truth) >",
      "`openspec/changes/` = what is PROPOSED (in flight, not yet true) >",
      "`openspec/changes/archive/` = superseded intent (NOT indexed — grep only if asked).",
      "",
      `## Capabilities — ${caps.length} specified (openspec/specs/<slug>/spec.md)`,
      "",
    ];
    const placeholders = caps.filter((c) => c.purposeIsPlaceholder).length;
    if (placeholders) {
      L.push(
        `_${placeholders}/${caps.length} specs have a placeholder Purpose — for those the ` +
          `line below is their first requirement title, not a written summary._`,
        "",
      );
    }
    for (const c of caps) {
      L.push(`- **${c.slug}** (${c.requirements.length} req) — ${clip(c.headline, 170)}`);
    }

    L.push("", `## Active changes — ${changes.length} in flight (NOT yet truth)`, "");
    for (const c of changes) {
      L.push(`### change:${c.slug} — ${c.progress}`);
      if (c.why) L.push(`- why: ${c.why}`);
      for (const w of c.what) L.push(`  - ${w}`);
    }

    const research = this.research();
    if (research.length) {
      L.push(
        "",
        `## Research — ${research.length} investigations, OLDEST FIRST`,
        "",
        "These are **measurements and conclusions from a given day**, not specifications.",
        "They perish. Two rules when citing one:",
        "",
        "1. **Always say the date.** \"The March benchmark found X\" is honest; \"X is true\" is not.",
        "2. **Check the family.** Docs marked `[SUPERSEDED?]` have a LATER round in the same",
        "   family — read that one before quoting the older number, because it may have been",
        "   re-measured and overturned. `[CURRENT]` is the latest word in its family.",
        "",
        "The full text is on disk — grep it when a number actually matters. What follows is",
        "the map: what was investigated, when, what it concluded, and what it builds on.",
        "",
      );
      for (const d of research) {
        const flag = d.isLatestOfFamily ? "[CURRENT]" : "[SUPERSEDED?]";
        L.push(`### ${d.date} — ${d.title} ${flag}`);
        L.push(`- file: \`${d.file}\` · family: \`${d.family}\``);
        if (d.refs.length) L.push(`- builds on / cites: ${d.refs.map((r) => `\`${r}\``).join(", ")}`);
        for (const c of d.conclusions) L.push(`  - ${c}`);
        L.push("");
      }
    }

    const rules = this.rules();
    if (rules.length) {
      L.push("", "## Binding rules (.claude/rules)", "");
      for (const r of rules) L.push(`- **${r.title}** (${r.file})`);
    }

    const guides = this.guides();
    if (guides.length) {
      L.push("", "## Guide / reference pages", "");
      for (const g of guides) L.push(`- **${g.domain}** (${g.file}) — ${g.keyFacts.join(", ")}`);
    }

    const fixes = this.recentFixes();
    if (fixes.length) {
      L.push("", "## Recent fixes (30d)", "");
      for (const f of fixes) L.push(`- ${f.description}`);
    }

    return L.join("\n");
  }
}

export default function createOpenSpecAdapter(ctx) {
  return new OpenSpecAdapter(ctx);
}
