/**
 * The tile's excerpt, made readable — raised 2026-08-19.
 *
 * The excerpt is the tile's answer to *what is happening here*, and on the
 * busiest agent it was the least readable thing on the screen: a session
 * writing a markdown table produced
 * `| |---|---| | **7.7** utasítás | input a csempén; három mező külön`, which
 * is pipes and asterisks where a sentence should be.
 *
 * **Line-level stripping, not markdown rendering.** The distinction is the
 * whole design:
 *
 *  - a renderer would need the WHOLE document to be correct, and an excerpt is
 *    a fragment by definition — it starts mid-table and ends mid-sentence, so
 *    any parser is being fed input it cannot parse and will guess;
 *  - a renderer produces STRUCTURE (headings, tables, code blocks) inside a
 *    two-line clamp, which is more layout, not less noise;
 *  - and it would put an agent's text through an HTML path. The text may be a
 *    consumer's own words; the fewer transformations, the fewer places it can
 *    be persisted or re-emitted by accident.
 *
 * So this removes the marks and keeps the words. Nothing is interpreted, no
 * document model is built, and a line that carries no words after stripping is
 * dropped rather than rendered as an empty row — a separator line (`|---|---|`)
 * says nothing at all once its pipes are gone.
 *
 * ⚠ It never adds, shortens or paraphrases. Clamping stays with the layout,
 * where the reader can widen it; a summariser here would make the tile state
 * something the agent did not say.
 */

/** A line that is only table scaffolding: `|---|:---:|---|`. */
const SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/

/** A fenced code block's delimiter, with or without a language. */
const FENCE = /^\s*(```|~~~)/

function stripInline(line: string): string {
  return line
    // Bold, italic and strikethrough marks — the words between them stay.
    .replace(/\*\*\*(.+?)\*\*\*/g, '$1')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/(^|[^*])\*(?!\s)([^*]+?)\*/g, '$1$2')
    .replace(/~~(.+?)~~/g, '$1')
    // Inline code: the code is the content, the backticks are not.
    .replace(/`{1,3}([^`]+)`{1,3}/g, '$1')
    // A link keeps its text and drops the target — the target is never
    // clickable here and doubles the length of the line.
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    // Leading heading marks, quote marks and list bullets.
    .replace(/^\s{0,3}#{1,6}\s+/, '')
    .replace(/^\s{0,3}>\s?/, '')
    .replace(/^\s{0,3}[-*+]\s+/, '· ')
    .replace(/^\s{0,3}(\d+)\.\s+/, '$1. ')
}

function stripTableRow(line: string): string {
  const t = line.trim()
  if (!t.startsWith('|')) return line
  // Cells joined by a middle dot: a table row read aloud, not a table.
  return t.replace(/^\||\|$/g, '').split('|').map(c => c.trim()).filter(Boolean).join(' · ')
}

/**
 * Strip markdown marks from an excerpt, line by line.
 *
 * Returns the words. An empty result means the fragment was ALL scaffolding,
 * which the caller must render as an absence rather than as a blank line — the
 * same rule the excerpt already follows for a tail of pure tool traffic.
 */
export function plainExcerpt(text: string | null | undefined): string {
  if (!text) return ''
  const out: string[] = []
  for (const raw of text.split('\n')) {
    if (FENCE.test(raw)) continue
    if (SEPARATOR.test(raw)) continue
    const line = stripInline(stripTableRow(raw)).trim()
    if (line) out.push(line)
  }
  // Collapse runs of spaces left behind by removed marks, and join the lines
  // with a single space: the tile clamps to a couple of lines anyway, and a
  // fragment's own line breaks are an artefact of where the tail was cut.
  return out.join(' ').replace(/\s{2,}/g, ' ').trim()
}
