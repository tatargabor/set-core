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
 *
 * ## The excerpt arrives as ONE line — measured 2026-08-19, after this shipped
 *
 * The first version was line-level only, and on the live screen it changed
 * nothing: the tile still read `Kész, két commit: | | | |---|---| | 7c9d3ec |`.
 * The producer joins the tail into a single string — **8 of 8 live excerpts
 * carry no newline at all** — so a table row never begins a line, a rule row is
 * never a line of its own, and a heading mark never sits at a line's start.
 * Every rule fired on a shape that does not occur.
 *
 * Its tests passed throughout, because they were written with the shape the
 * function was designed for. That is the mechanism-versus-result split: the
 * stripping worked, and the screen was unchanged. Both shapes are handled now,
 * and the joined one is the case the fixtures below are taken from.
 */

/** A line that is only table scaffolding: `|---|:---:|---|`. */
const SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/

/**
 * A table's rule row, wherever it sits — `|---|---|`.
 *
 * It is also the TELL that pipes on this line are table cells rather than shell
 * pipes. `pgrep -af x | grep y` is ordinary prose on this screen and must
 * survive; a line carrying a rule was a table before somebody joined it.
 */
const TABLE_RULE = /\|(?:\s*:?-{2,}:?\s*\|)+/

/**
 * The same tell, cut off — `… | most | |--…` at the end of a fragment.
 *
 * Measured on the live screen after the joined-line fix shipped: the producer
 * truncates the tail and appends an ellipsis, so a table whose header row
 * survived can lose its rule's closing pipe. The complete-rule pattern then
 * matched nothing and the pipes stayed on screen — the same defect one step
 * further along, and again found by looking rather than by a test.
 *
 * Anchored to the END, and the tail may hold nothing but dashes: `ls | grep
 * --color` keeps its pipe because letters follow the dashes, which is the case
 * this anchor exists to protect.
 */
const TABLE_RULE_CUT = /\|\s*:?-{2,}:?\s*(?:…|\.{3})?\s*$/

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
    // Heading marks — anywhere, not only at a line's start. A joined excerpt
    // carries `… dev-re ## Two commits …` mid-sentence, and requiring the start
    // of a line meant the mark stayed on every real excerpt.
    .replace(/(^|\s)#{1,6}\s+/g, '$1')
    // Quote marks and list bullets, which only mean anything at a line's start.
    .replace(/^\s{0,3}>\s?/, '')
    .replace(/^\s{0,3}[-*+]\s+/, '· ')
    .replace(/^\s{0,3}(\d+)\.\s+/, '$1. ')
}

function stripTable(line: string): string {
  const t = line.trim()
  // Either shape: a row that begins a line, or a whole table flattened into
  // one. Without the rule, a lone `|` is left alone — see TABLE_RULE.
  if (!t.startsWith('|') && !TABLE_RULE.test(t) && !TABLE_RULE_CUT.test(t)) return line
  // Cells joined by a middle dot: a table read aloud, not a table. Empty cells
  // drop out, which is what the `| | |` runs of a flattened table are.
  return t
    .replace(new RegExp(TABLE_RULE.source, 'g'), '|')
    .replace(TABLE_RULE_CUT, '')
    .split('|').map(c => c.trim()).filter(Boolean).join(' · ')
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
    const line = stripInline(stripTable(raw)).trim()
    if (line) out.push(line)
  }
  // Collapse runs of spaces left behind by removed marks, and join the lines
  // with a single space: the tile clamps to a couple of lines anyway, and a
  // fragment's own line breaks are an artefact of where the tail was cut.
  return out.join(' ').replace(/\s{2,}/g, ' ').trim()
}
