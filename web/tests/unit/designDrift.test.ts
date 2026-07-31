/**
 * Design-system drift — the mechanical rules, asserted against the source tree.
 *
 * This file exists because the rules it checks were written down once, archived as the
 * `tui-design-system` capability, and then quietly stopped being true. Measured on the day it
 * was written: 68 arbitrary font sizes across 11 files and 34 `font-mono` usages, against a
 * specification that had forbidden both since it was archived. A rule nothing measures does not
 * hold, and this one had demonstrated that for as long as it existed.
 *
 * WHAT THIS FILE DOES NOT COVER, stated here because a checker's name is the part that travels:
 * it does not check the HUED colour classes — `text-red-400`, `text-green-400` and their
 * neighbours. Those still appear in the tree. Each one needs a per-site judgement about whether
 * it means a state, a log category, or nothing in particular, and a sweep that guessed would
 * write the wrong meaning into the token layer permanently. The neutrals ARE covered, because
 * "how loud is this text" is decidable without reading the surrounding feature.
 *
 * So: a green run here means the three rules below hold. It does not mean the design system is
 * fully enforced, and nothing in this file may be quoted as saying so.
 */
import { describe, expect, it } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../src')

/**
 * Exemptions, as an explicit list with a reason each.
 *
 * Never as a loosened pattern: a pattern wide enough to let Battle through is wide enough to
 * let the next violation through too, and nobody would be told.
 */
const EXEMPT: { path: string; why: string }[] = [
  {
    path: 'components/battle',
    why: 'The Battle view has independent styling by a prior decision that predates this system.',
  },
]

/**
 * This file itself.
 *
 * It contains every banned pattern as a string literal, so without excluding it the checker
 * reports itself and fails permanently. Excluded by exact filename rather than by a substring
 * anyone else could match: `test` or `drift` would also silence a future file that genuinely
 * needs checking, and the direction of that mistake is silence.
 */
const SELF = 'designDrift.test.ts'

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    const rel = path.relative(SRC, full)
    if (EXEMPT.some(e => rel === e.path || rel.startsWith(e.path + path.sep))) continue
    if (statSync(full).isDirectory()) { sourceFiles(full, out); continue }
    if (!/\.tsx?$/.test(entry) || entry === SELF) continue
    out.push(full)
  }
  return out
}

/** Every `(file, line, text)` in the tree whose line matches. */
function hits(re: RegExp): string[] {
  const found: string[] = []
  for (const f of sourceFiles(SRC)) {
    readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
      if (re.test(line)) found.push(`${path.relative(SRC, f)}:${i + 1}: ${line.trim().slice(0, 100)}`)
    })
  }
  return found
}

describe('design-system drift', () => {
  it('carries no arbitrary font size — the scale is 12/14/16', () => {
    // `text-[13px]` and friends. The smallest thing on this surface was once 8px.
    expect(hits(/text-\[\d+px\]/)).toEqual([])
  })

  it('carries no font-mono class — the global font is already monospace', () => {
    expect(hits(/\bfont-mono\b/)).toEqual([])
  })

  it('names a neutral by meaning, not by shade', () => {
    // `text-neutral-400` says how dark. `text-fg-muted` says how loud, which is the thing a
    // reader is actually being told and the thing a second surface would need to restyle.
    expect(hits(/\b(?:text|bg|border)-neutral-\d{2,3}\b/)).toEqual([])
  })

  it('the exemption list states a reason for every entry', () => {
    // An exemption without a reason becomes permanent by default: nobody can tell whether it
    // was a decision or an oversight, so nobody removes it.
    for (const e of EXEMPT) expect(e.why.length).toBeGreaterThan(20)
  })

  it('finds the files it claims to check', () => {
    // The zero above is only meaningful if the corpus is non-empty. A checker that walks
    // nothing reports clean, and reports it exactly as confidently as one that walked
    // everything — this is the shape that lets a broken check look like a passing one.
    const files = sourceFiles(SRC)
    expect(files.length).toBeGreaterThan(50)
    expect(files.some(f => f.endsWith('.tsx'))).toBe(true)
    // The EXEMPT DIRECTORY is excluded — not every path containing the word. `lib/battleScoring.ts`
    // lives outside `components/battle` and is checked like anything else; asserting on the word
    // would have quietly exempted three more files than anyone decided to exempt.
    expect(files.every(f => !f.includes(`components${path.sep}battle`))).toBe(true)
    expect(files.every(f => !f.endsWith(SELF))).toBe(true)
  })
})
