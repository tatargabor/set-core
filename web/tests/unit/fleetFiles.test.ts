/**
 * The three decisions the file view rests on, measured without a browser.
 *
 * `fileReference` gets most of the attention because it is the one fed by text
 * somebody else wrote: everything in a terminal was produced by whatever the
 * agent ran, so what this function is willing to call a path is a boundary, not
 * a convenience.
 */
import { describe, expect, it } from 'vitest'

import { buildTree, fileReference, languageOf, fileToOpen } from '../../src/lib/fleetFiles'

describe('a flat listing becomes a structure', () => {
  it('nests directories and keeps a stable order', () => {
    const tree = buildTree(['src/b.ts', 'README.md', 'src/a.ts', 'src/deep/x.ts'])
    // Directories first, then files, each alphabetical — an order that changes
    // between renders is one nobody can find anything in twice.
    expect(tree.map(n => n.name)).toEqual(['src', 'README.md'])
    const src = tree[0]
    expect(src.dir).toBe(true)
    expect(src.children!.map(n => n.name)).toEqual(['deep', 'a.ts', 'b.ts'])
    expect(src.children![0].children!.map(n => n.path)).toEqual(['src/deep/x.ts'])
  })

  it('gives every node the full path, not just its own name', () => {
    // The path is what the endpoint is asked for. A node carrying only its name
    // would need its parents walked at click time — a second derivation of
    // something already known here.
    const tree = buildTree(['a/b/c.ts'])
    expect(tree[0].path).toBe('a')
    expect(tree[0].children![0].path).toBe('a/b')
    expect(tree[0].children![0].children![0].path).toBe('a/b/c.ts')
  })

  it('does not merge a file and a directory that share a name', () => {
    const tree = buildTree(['x', 'x/y.ts'])
    expect(tree.filter(n => n.name === 'x').length).toBe(2)
    expect(tree.some(n => n.name === 'x' && n.dir)).toBe(true)
    expect(tree.some(n => n.name === 'x' && !n.dir)).toBe(true)
  })
})

describe('what language a file is', () => {
  it('names the common ones', () => {
    expect(languageOf('src/a.tsx')).toBe('typescript')
    expect(languageOf('lib/set_orch/api/files.py')).toBe('python')
    expect(languageOf('openspec/bugs/README.md')).toBe('markdown')
    expect(languageOf('Dockerfile')).toBe('dockerfile')
  })

  it('answers "no colours" rather than failing for an unknown type', () => {
    // `undefined` is a real answer: the file opens as plain text. An unknown
    // extension must never be a file that refuses to open.
    expect(languageOf('data.bin')).toBeUndefined()
    expect(languageOf('LICENSE')).toBeUndefined()
  })
})

describe('a file reference in terminal output', () => {
  const root = '/home/x/proj'
  const known = new Set(['src/app.ts', 'README.md', 'a.b', 'deep/nested/file.py'])

  it('reads the path:line shape this repo prints', () => {
    expect(fileReference('src/app.ts:214', root, known)).toEqual({ path: 'src/app.ts', line: 214 })
    expect(fileReference('src/app.ts:214:8', root, known)).toEqual({ path: 'src/app.ts', line: 214 })
  })

  it('reads a plain path, and one written relative to here', () => {
    expect(fileReference('README.md', root, known)).toEqual({ path: 'README.md' })
    expect(fileReference('./README.md', root, known)).toEqual({ path: 'README.md' })
  })

  it('reads an absolute path inside the project', () => {
    expect(fileReference('/home/x/proj/src/app.ts:3', root, known))
      .toEqual({ path: 'src/app.ts', line: 3 })
  })

  it('refuses an absolute path outside the project', () => {
    // Printed by the agent, and therefore not a thing the dashboard offers to
    // open — the framework may only read inside a project it knows.
    expect(fileReference('/etc/shadow', root, known)).toBeNull()
    expect(fileReference('/home/x/proj-other/src/app.ts', root, known)).toBeNull()
  })

  it('is not fooled by a prefix that merely starts the same', () => {
    // The refuted implementation, held here rather than described: comparing
    // with `startsWith(root)` and no path boundary. `/home/x/projX` starts with
    // `/home/x/proj`.
    expect(fileReference('/home/x/projX/src/app.ts', root, known)).toBeNull()
  })

  it('refuses a path the project does not have', () => {
    // Guessing would produce a link that fails on click, and a control that
    // fails on click is worse than no control.
    expect(fileReference('src/imaginary.ts', root, known)).toBeNull()
    expect(fileReference('src/imaginary.ts:12', root, known)).toBeNull()
  })

  it('does not turn a clock or a URL into a file', () => {
    // The colon has two meanings in this text and only one of them is a line
    // number. Both of these split cleanly into `path:digits` and must not.
    expect(fileReference('12:30', root, known)).toBeNull()
    expect(fileReference('http://localhost:7400', root, known)).toBeNull()
  })

  it('keeps a real file whose own name contains a colon-shaped tail', () => {
    // `a.b` is a file this project has. The `path:line` split must be tried and
    // then DISBELIEVED when the path part is not a known file — which is why the
    // whole token is a candidate too.
    expect(fileReference('a.b', root, known)).toEqual({ path: 'a.b' })
  })

  it('drops the punctuation a sentence leaves on a path', () => {
    expect(fileReference('(src/app.ts)', root, known)).toEqual({ path: 'src/app.ts' })
    expect(fileReference('README.md,', root, known)).toEqual({ path: 'README.md' })
    // ...but not a trailing `:line`, which is not punctuation.
    expect(fileReference('src/app.ts:9', root, known)).toEqual({ path: 'src/app.ts', line: 9 })
  })

  it('says nothing about an empty or blank token', () => {
    expect(fileReference('', root, known)).toBeNull()
    expect(fileReference('   ', root, known)).toBeNull()
  })
})

/**
 * WHERE THE READER WAS — the panel is closed and re-opened.
 *
 * Asked for 2026-08-22. The interesting half is the refusal: a control that
 * restores the last file MUST NOT do so when a file was actually named, or every
 * ctrl-click after the first one opens the wrong file — and it would do it
 * quietly, which is the shape that gets reported as "the links stopped working".
 */
describe('which file opening the panel opens', () => {
  it('restores where the reader was when no file is named', () => {
    expect(fileToOpen({ path: '' }, { path: 'src/a.ts', line: 12 }))
      .toEqual({ path: 'src/a.ts', line: 12 })
  })

  it('opens the file that WAS named, ignoring where the reader was', () => {
    expect(fileToOpen({ path: 'src/b.ts' }, { path: 'src/a.ts', line: 12 }))
      .toEqual({ path: 'src/b.ts' })
  })

  it('changes nothing when there is nothing remembered', () => {
    expect(fileToOpen({ path: '' }, null)).toEqual({ path: '' })
    expect(fileToOpen({ path: '' })).toEqual({ path: '' })
  })
})
