/**
 * Colour that distinguishes without judging.
 *
 * The surface was measured at 0.15 % hued pixels against a sibling screen's 2.14 % — ten times
 * less colour, and almost all of what it had was one button. The cause is not taste: the sibling
 * knows what its own states mean and may colour them, while this renderer must never learn any
 * project's vocabulary. So the colour is derived from CARDINALITY, which needs no vocabulary.
 *
 * The tests below are weighted toward what could go WRONG with that, because the danger is not an
 * ugly screen. It is a hue that reads as a verdict the renderer never measured.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { categoryTints } from '../../src/components/StatusTable'

const bugs = [
  { id: 'a', severity: 'HIGH', status: 'FIXED', title: 'one' },
  { id: 'b', severity: 'LOW', status: 'OPEN', title: 'two' },
  { id: 'c', severity: 'HIGH', status: 'FIXED', title: 'three' },
  { id: 'd', severity: 'MEDIUM', status: 'FIXED', title: 'four' },
]
const cols = ['id', 'severity', 'status', 'title']

describe('categoryTints', () => {
  it('tints a column that repeats a few values', () => {
    const t = categoryTints(bugs, cols)
    expect(t.has('severity')).toBe(true)
    expect(t.has('status')).toBe(true)
  })

  it('gives one hue per value, and the same hue to equal values', () => {
    const sev = categoryTints(bugs, cols).get('severity')!
    expect(sev.get('HIGH')).toBe(sev.get('HIGH'))
    expect(sev.get('HIGH')).not.toBe(sev.get('LOW'))
    expect(new Set(sev.values()).size).toBe(3)
  })

  it('assigns the hue by sorted order, so it survives sorting and filtering', () => {
    // A colour that moved when the reader sorted would be worse than no colour: they would be
    // tracking a hue that no longer means the same row. Row order is varied here on purpose.
    const reordered = [bugs[3], bugs[1], bugs[2], bugs[0]]
    const a = categoryTints(bugs, cols).get('severity')!
    const b = categoryTints(reordered, cols).get('severity')!
    for (const k of a.keys()) expect(b.get(k)).toBe(a.get(k))
  })

  it('leaves a column of unique values alone', () => {
    // Every row a different hue is noise wearing a code's clothes — there is no group to see.
    expect(categoryTints(bugs, cols).has('id')).toBe(false)
    expect(categoryTints(bugs, cols).has('title')).toBe(false)
  })

  it('never tints a quantity', () => {
    // Found by looking at the screen, not by reasoning: a `count` column of 25 / 9 / 27 passed
    // every cardinality test and rendered in three hues, reading as a scale. The palette carries
    // no scale, so a tint there would imply an ordering the renderer never measured.
    const rows = [{ count: 25 }, { count: 9 }, { count: 27 }, { count: 25 }]
    expect(categoryTints(rows, ['count']).has('count')).toBe(false)
  })

  it('never tints a boolean, which already has a meaning-bearing colour', () => {
    const rows = [{ ok: true }, { ok: false }, { ok: true }, { ok: false }]
    expect(categoryTints(rows, ['ok']).has('ok')).toBe(false)
  })

  it('gives up rather than run out of palette', () => {
    // Seven near-hues stop being a code the reader can hold. Plain is the honest outcome — a tint
    // nobody can decode is decoration claiming to be information.
    const rows = Array.from({ length: 14 }, (_, i) => ({ k: `v${i % 7}` }))
    expect(categoryTints(rows, ['k']).has('k')).toBe(false)
  })

  it('leaves prose alone even when it repeats', () => {
    const rows = Array.from({ length: 6 }, (_, i) => ({
      note: i % 2 ? 'a sentence long enough to be prose rather than a label' : 'another such sentence',
    }))
    expect(categoryTints(rows, ['note']).has('note')).toBe(false)
  })

  it('uses no hue this surface has already given a meaning', () => {
    // The load-bearing test. Amber says something is withheld, emerald says true, red says failed,
    // blue is an action you can take. A category hue must be able to distinguish and must NOT be
    // able to imply a verdict — so it may not reuse any of them, whatever the palette grows into.
    const classes = [...categoryTints(bugs, cols).values()].flatMap(m => [...m.values()])
    expect(classes.length).toBeGreaterThan(0)
    for (const c of classes) {
      expect(c).not.toMatch(/amber|emerald|green|red|rose|blue-/)
      expect(c).toMatch(/text-cat-[1-6]$/)
    }
  })

  it('names the classes as literals, because an interpolated one compiles to nothing', () => {
    // Tailwind emits a utility only when the class name appears verbatim in the source. The first
    // version built `text-cat-${i}` — the map filled, the class reached the cell, and the
    // stylesheet held zero `text-cat-*` rules. Every part of the mechanism worked and the screen
    // did not change. This asserts the shape that made it compile, so a later tidy-up back to
    // interpolation fails here instead of silently rendering nothing.
    const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../src/components/StatusTable.tsx')
    const text = readFileSync(src, 'utf8')
    expect(text).toContain("'[&_span]:text-cat-1'")

    // Comments are stripped before the pattern runs, and the first version of THIS test failed
    // without it — the doc comment explaining the bug names the interpolated form, so the check
    // matched its own explanation. The measurement was inside the corpus it measured, which is
    // the same shape as a `pgrep` matching the shell that ran it: it over-reports, and the
    // obvious repair is to delete the sentence that made the finding findable.
    const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
    expect(code).toContain("'[&_span]:text-cat-1'")
    expect(code).not.toMatch(/text-cat-\$\{/)
  })
})
