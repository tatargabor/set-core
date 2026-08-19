/**
 * The tile's excerpt, stripped of markdown marks — raised 2026-08-19 from the
 * live screen: the busiest agent's excerpt read
 * `| |---|---| | **7.7** utasítás | input a csempén; három mező külön`.
 *
 * The rule under every case: **remove the marks, keep the words.** Nothing is
 * interpreted, nothing is summarised, and nothing is added — the excerpt is the
 * tile's answer to *what is happening*, and a function that rewrote it would
 * make the tile state something the agent did not say.
 */
import { describe, expect, it } from 'vitest'

import { plainExcerpt } from '../../src/lib/excerptText'

describe('markdown marks go, words stay', () => {
  it('reads a table row as a sentence instead of pipes', () => {
    expect(plainExcerpt('| **7.7** instruction | input on the tile | three fields |'))
      .toBe('7.7 instruction · input on the tile · three fields')
  })

  it('drops a separator row entirely — it carries no words at all', () => {
    expect(plainExcerpt('| a | b |\n|---|---|\n| 1 | 2 |')).toBe('a · b 1 · 2')
  })

  it('strips bold, italic, strikethrough and inline code', () => {
    expect(plainExcerpt('**done** and *pending* and ~~dropped~~ and `code`'))
      .toBe('done and pending and dropped and code')
  })

  it('keeps a link’s text and drops its target', () => {
    expect(plainExcerpt('see [the record](docs/integration/consumer.md) first'))
      .toBe('see the record first')
  })

  it('strips heading, quote and list marks', () => {
    expect(plainExcerpt('## What shipped\n> a quote\n- first\n2. second'))
      .toBe('What shipped a quote · first 2. second')
  })

  it('drops code fences but keeps what is inside them', () => {
    expect(plainExcerpt('```bash\nnpm test\n```')).toBe('npm test')
  })

  /**
   * The absence case. An excerpt made ENTIRELY of scaffolding leaves nothing,
   * and the caller must render that as an absence rather than as a blank line —
   * the same rule the excerpt already follows for a tail of pure tool traffic.
   */
  it('returns nothing when the fragment was all scaffolding', () => {
    expect(plainExcerpt('|---|---|')).toBe('')
    expect(plainExcerpt('```')).toBe('')
    expect(plainExcerpt(null)).toBe('')
  })

  /**
   * The refuted alternative, held here: rendering markdown. An excerpt is a
   * FRAGMENT — it starts mid-table and ends mid-sentence — so a parser is
   * always being fed input it cannot parse, and it produces structure inside a
   * two-line clamp. This function is asserted to be a strip, not a renderer:
   * no tags come out of it.
   */
  it('produces no markup, only text', () => {
    const out = plainExcerpt('# Title\n| **a** | `b` |\n[x](y)')
    expect(out).not.toMatch(/[<>]/)
    expect(out).toBe('Title a · b x')
  })

  it('leaves ordinary prose untouched', () => {
    const prose = 'Kész, két commit ment be — a suite zöld, a build lefutott.'
    expect(plainExcerpt(prose)).toBe(prose)
  })

  /**
   * The shape the producer ACTUALLY sends — measured 2026-08-19 on the live
   * endpoint: **8 of 8 excerpts carried no newline at all.** The tail is joined
   * before it leaves the producer, so a table row never begins a line and a
   * rule row is never a line of its own.
   *
   * The refuted implementation is the one that shipped first: line-level rules
   * only. Every case above passed with it and the screen was unchanged —
   * `Kész, két commit: | | | |---|---| | 7c9d3ec |` still read as pipes. Held
   * here so a later tidy-up back to "one rule per line" fails instead of
   * looking identical and quietly stripping nothing.
   */
  it('reads a whole table flattened into ONE line', () => {
    expect(plainExcerpt('Ready, two commits: | | | |---|---| | `7c9d3ec` | the rule went into the doc |'))
      .toBe('Ready, two commits: · 7c9d3ec · the rule went into the doc')
  })

  it('strips a heading mark that lost its line', () => {
    expect(plainExcerpt('Done. **Nothing hidden.** ## Two commits landed on `dev` and that is all'))
      .toBe('Done. Nothing hidden. Two commits landed on dev and that is all')
  })

  /**
   * The other direction, and the reason the rule row is the tell: a shell pipe
   * is ordinary prose on this screen. Stripping every `|` would rewrite a
   * command into something that does not run.
   */
  it('leaves a shell pipe alone when no table rule says otherwise', () => {
    expect(plainExcerpt('the check is `pgrep -af x | grep -c y` and it over-reports'))
      .toBe('the check is pgrep -af x | grep -c y and it over-reports')
  })

  it('does not eat an asterisk used as a word', () => {
    expect(plainExcerpt('the glob is *.ts and it matched 12 files'))
      .toBe('the glob is *.ts and it matched 12 files')
  })
})
