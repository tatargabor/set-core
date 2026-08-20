/**
 * The product is in ENGLISH — the rule, as a check rather than as prose.
 *
 * Stated by the user on 2026-08-19: set-core and every open-source `set-*`
 * project are English, because these repositories are public and a framework
 * nobody outside one language can read is a framework nobody outside it can
 * use. The consumer projects are the Hungarian ones — the same split the
 * abstraction already draws.
 *
 * **It was prose for one day and it failed on the second.** Found 2026-08-20 by
 * LOOKING at the running fleet screen: `{totals.working} dolgozik` sat beside
 * `unknown` and `waiting for a human`, one Hungarian word in a panel of English.
 * No test could have caught it, and none tried: a test that asserts the wrong
 * language passes exactly as well as one asserting the right one, so a suite is
 * blind to this by construction unless something checks the SOURCE.
 *
 * ## What this checks — and the FIRST version of it could not have caught the
 * word that caused it
 *
 * Not "is this English" — undecidable, and a checker that guessed would either
 * fire constantly or never. The mechanical half is **Hungarian-specific
 * letters**: `á é í ó ö ő ú ü ű` do not occur in English, so a rendered string
 * carrying one is Hungarian with near-certainty.
 *
 * ⚠ **`dolgozik` has no accent.** The accent rule alone would have reported a
 * clean tree on the very day this file was written, about the very word it was
 * written for — a checker whose name promises more than its mechanism does, in
 * the same breath as being written to stop exactly that. Hence the second half:
 * a small, curated list of Hungarian words that do not collide with English.
 *
 * The list is deliberately short and deliberately explicit. It cannot be
 * complete, and a longer one would start colliding — so a green run here means
 * *no accented Hungarian and none of these words reach the screen*, and it may
 * not be quoted as *the UI is English*. The real check is a person looking, and
 * that is what found this one.
 *
 * ## What is deliberately NOT a violation
 *
 * Comments and docstrings. This repository's rules make the exception
 * explicitly, and it is load-bearing rather than lenient: **a verbatim quote of
 * the user is evidence, and paraphrasing it into English destroys what it
 * carries.** Most Hungarian in this tree is exactly that — the sentence that
 * caused a change, kept next to the code it caused.
 */
import { describe, expect, it } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../src')
const ACCENTS = /[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]/

/**
 * Hungarian words that carry no accent and no English meaning.
 *
 * Curated, never generated: every entry is a word that cannot appear in an
 * English UI string, so a hit is a finding rather than a coincidence. `van`,
 * `sor`, `perc` and their like are deliberately ABSENT — they collide with
 * English words or fragments, and a checker that cries wolf is one somebody
 * disables. Add to this only after checking the word against the tree.
 */
const HU_WORDS = [
  'dolgozik', 'nincs', 'vannak', 'projektben', 'ugynok', 'csempe', 'keszult',
  'hiba', 'beallitas', 'valasz', 'kerdes', 'futtatas', 'megnyitas', 'bezaras',
  'toltes', 'mentes', 'torles', 'ervenyes', 'ismeretlen', 'varakozik',
]
const HU_WORD = new RegExp(`\\b(${HU_WORDS.join('|')})\\b`, 'i')

/** Either signal. Both are narrow; neither claims to decide "is this English". */
const HU = { test: (s: string) => ACCENTS.test(s) || HU_WORD.test(s) }
const SELF = 'uiLanguage.test.ts'

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) { sourceFiles(full, out); continue }
    if (/\.tsx?$/.test(entry) && entry !== SELF) out.push(full)
  }
  return out
}

/**
 * Strip comments, keep code.
 *
 * Deliberately crude and deliberately biased: a `//` inside a string literal
 * (a URL) would truncate that line, which loses a candidate rather than
 * inventing one. Failing towards *misses a violation* is survivable here
 * because a person looking is the real check; failing towards *invents one*
 * would get this file disabled, and a disabled gate is worse than none.
 */
function code(src: string): string[] {
  // Blank the block comments, do NOT delete them: removing the newlines shifts
  // every line number after the first comment, and this checker's whole output
  // is a list of file:line. Measured the first time it ran — it reported
  // `Fleet.tsx:707` for a string on line 949, which sends the reader to
  // unrelated code and reads as a checker that cannot be trusted.
  const blanked = src.replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' '))
  return blanked.split('\n').map(l => l.replace(/\/\/.*$/, ''))
}

/** A string literal or a JSX text run — what a reader could end up seeing. */
function renderedText(line: string): string[] {
  const out: string[] = []
  for (const m of line.matchAll(/'([^']*)'|"([^"]*)"|`([^`]*)`/g)) {
    out.push(m[1] ?? m[2] ?? m[3] ?? '')
  }
  // JSX text between tags, e.g. `>{n} dolgozik<` — the case that was missed.
  for (const m of line.matchAll(/>([^<>{}]+)</g)) out.push(m[1])
  // …and the trailing half of `{expr} text` inside JSX, which has no closing
  // `<` on the same line. This is the exact shape of the word that got through.
  for (const m of line.matchAll(/\}([A-Za-zÀ-ſ ,.:;!?'-]{2,})$/g)) out.push(m[1])
  return out
}

describe('no accented Hungarian reaches the screen', () => {
  it('carries none in any rendered string under src/', () => {
    const offenders: string[] = []
    for (const file of sourceFiles(SRC)) {
      const rel = path.relative(SRC, file)
      code(readFileSync(file, 'utf8')).forEach((line, i) => {
        for (const text of renderedText(line)) {
          if (HU.test(text)) offenders.push(`${rel}:${i + 1}  ${text.trim().slice(0, 70)}`)
        }
      })
    }
    expect(offenders, 'Hungarian in a rendered string — the product is English:\n' + offenders.join('\n')).toEqual([])
  })

  /**
   * The detector proven to FIRE before its zero is believed. A checker that
   * reports clean is indistinguishable from one that cannot report anything,
   * and this one's regexes are the fragile part.
   */
  it('catches the exact line that got through, accent or no accent', () => {
    const line = '              <span className="w-2 h-2 rounded-full bg-emerald-400" />{totals.working} dolgozik'
    expect(
      renderedText(line).some(t => HU.test(t)),
      'the checker cannot see the word it was written for',
    ).toBe(true)
  })

  /**
   * ⚠ HOLDS THE WEAKER MECHANISM, so a later "simplification" back to accents
   * alone fails here instead of looking identical and quietly checking less.
   * The accent rule reported this line clean — which is why the word list
   * exists at all.
   */
  it('records that the accent rule ALONE would have reported it clean', () => {
    const line = '<span />{totals.working} dolgozik'
    expect(renderedText(line).some(t => ACCENTS.test(t))).toBe(false)
  })

  /**
   * The line number must point at the STRING, not at wherever the arithmetic
   * landed. A checker whose report sends the reader to unrelated code is worse
   * than one that says nothing: the first thing they learn is that it lies.
   */
  it('reports the line the string is actually on', () => {
    const src = ['const a = 1', '/* a', '   block', '   comment */', "const b = 'nincs'"].join('\n')
    const lines = code(src)
    expect(lines).toHaveLength(5)
    const hit = lines.findIndex(l => renderedText(l).some(t => HU.test(t)))
    expect(hit + 1).toBe(5)
  })

  /** And it does NOT fire on a comment, which is where the quotes live. */
  it('leaves a verbatim quote in a comment alone', () => {
    const src = `/* raised: "nagyon összefolynak a dolgok, nincs hiba" */\nconst x = 'plain'\n// és ez is magyar, dolgozik\n`
    const found = code(src).flatMap(renderedText).filter(t => HU.test(t))
    expect(found).toEqual([])
  })
})
