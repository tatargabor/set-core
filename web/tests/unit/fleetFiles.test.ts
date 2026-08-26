/**
 * The three decisions the file view rests on, measured without a browser.
 *
 * `fileReference` gets most of the attention because it is the one fed by text
 * somebody else wrote: everything in a terminal was produced by whatever the
 * agent ran, so what this function is willing to call a path is a boundary, not
 * a convenience.
 */
import { describe, expect, it } from 'vitest'

import { buildTree, externalReference, fileReference, languageOf, fileToOpen } from '../../src/lib/fleetFiles'

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
 * A PATH THAT IS NOT THIS PROJECT'S — reported 2026-08-26.
 *
 * An agent prints where it put a screenshot, and it is almost never inside the
 * tree it is working in. `fileReference` refuses those, correctly: the framework
 * may not READ them. `externalReference` decides whether the same token may be
 * HANDED OVER to the desktop instead, so its refusals are about a different
 * question and every one of them is here.
 */
describe('an absolute path that is not this project\'s', () => {
  const root = '/home/x/proj'

  it('reads the reported case — a screenshot path inside parentheses', () => {
    expect(externalReference('(/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg)', root))
      .toBe('/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg')
  })

  it('drops a trailing line number, which no desktop handler can use', () => {
    // Kept as a path rather than refused: `/tmp/run.log:42` names a file that
    // exists, and refusing it would be a link that fails for a reason the reader
    // cannot see.
    expect(externalReference('/tmp/run.log:42', root)).toBe('/tmp/run.log')
    expect(externalReference('/tmp/run.log:42:7', root)).toBe('/tmp/run.log')
  })

  it('leaves this project\'s own files to the file view', () => {
    // Precedence lives HERE, not in whichever provider is registered first.
    expect(externalReference('/home/x/proj/src/app.ts', root)).toBeNull()
    expect(externalReference('/home/x/proj', root)).toBeNull()
  })

  it('is not fooled by a prefix that merely starts the same', () => {
    // The mirror image of `fileReference`'s own boundary test: `/home/x/projX`
    // is a DIFFERENT project, so it is external and must be offered.
    expect(externalReference('/home/x/projX/src/app.ts', root)).toBe('/home/x/projX/src/app.ts')
  })

  it('answers with no project context at all', () => {
    // A docked panel knows no root. An external path needs none, so the link is
    // still offered there — the degradation is that an in-project path is
    // offered as an external one, not that nothing works.
    expect(externalReference('/tmp/shot.png')).toBe('/tmp/shot.png')
  })

  it('refuses a URL, which belongs to the other link provider', () => {
    // Handing a URL to a desktop opener is how a scheme that was already
    // refused in the browser gets a second chance at being followed.
    expect(externalReference('http://localhost:7400/x', root)).toBeNull()
    expect(externalReference('file:///etc/passwd', root)).toBeNull()
  })

  it('refuses anything that is not one absolute path', () => {
    expect(externalReference('src/app.ts', root)).toBeNull()
    expect(externalReference('12:30', root)).toBeNull()
    expect(externalReference('', root)).toBeNull()
    expect(externalReference('   ', root)).toBeNull()
    expect(externalReference('/', root)).toBeNull()
    // `//host/share` is a UNC-shaped token, not a local path.
    expect(externalReference('//host/share', root)).toBeNull()
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
