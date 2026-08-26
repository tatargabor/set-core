/**
 * The three decisions the file view rests on, measured without a browser.
 *
 * `fileReference` gets most of the attention because it is the one fed by text
 * somebody else wrote: everything in a terminal was produced by whatever the
 * agent ran, so what this function is willing to call a path is a boundary, not
 * a convenience.
 */
import { describe, expect, it } from 'vitest'

import { ancestorsOf, buildTree, desktopReference, fileReference, languageOf, fileToOpen, statusKind, terminalTarget } from '../../src/lib/fleetFiles'

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
 * A PATH THE FILE VIEW CANNOT OPEN — reported 2026-08-26, twice.
 *
 * First an agent printed where it put a screenshot, and that is almost never
 * inside the tree it is working in. Then it printed a DIRECTORY —
 * `openspec/changes/<name>/` — which no listing ever contains, because a listing
 * carries files. `fileReference` refuses both, correctly: the framework may not
 * READ them. `desktopReference` decides whether the same token may be HANDED
 * OVER to the desktop instead, so its refusals are about a different question
 * and every one of them is here.
 */
describe('a path the file view cannot open', () => {
  const root = '/home/x/proj'

  it('reads the reported case — a screenshot path inside parentheses', () => {
    expect(desktopReference('(/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg)', root))
      .toBe('/tmp/claude-chrome-screenshots-DJPCLm/shot-2.jpg')
  })

  it('drops a trailing line number, which no desktop handler can use', () => {
    // Kept as a path rather than refused: `/tmp/run.log:42` names a file that
    // exists, and refusing it would be a link that fails for a reason the reader
    // cannot see.
    expect(desktopReference('/tmp/run.log:42', root)).toBe('/tmp/run.log')
    expect(desktopReference('/tmp/run.log:42:7', root)).toBe('/tmp/run.log')
  })

  it('does not decide precedence — it only names a path', () => {
    // It used to return null for anything inside the project root. That put the
    // decision in the wrong place: whether the file view can open a path depends
    // on the LISTING and on where the agent stands, neither of which this
    // function holds. `terminalTarget` decides; this one answers "which path".
    expect(desktopReference('/home/x/proj/src/app.ts', root)).toBe('/home/x/proj/src/app.ts')
  })

  it('is not fooled by a prefix that merely starts the same', () => {
    // The mirror image of `fileReference`'s own boundary test: `/home/x/projX`
    // is a DIFFERENT project, so it is external and must be offered.
    expect(desktopReference('/home/x/projX/src/app.ts', root)).toBe('/home/x/projX/src/app.ts')
  })

  it('answers with no project context at all', () => {
    // A docked panel knows no root. An external path needs none, so the link is
    // still offered there — the degradation is that an in-project path is
    // offered as an external one, not that nothing works.
    expect(desktopReference('/tmp/shot.png')).toBe('/tmp/shot.png')
  })

  it('refuses a URL, which belongs to the other link provider', () => {
    // Handing a URL to a desktop opener is how a scheme that was already
    // refused in the browser gets a second chance at being followed.
    expect(desktopReference('http://localhost:7400/x', root)).toBeNull()
    expect(desktopReference('file:///etc/passwd', root)).toBeNull()
  })

  it('resolves a relative DIRECTORY against the project root — the reported case', () => {
    // `openspec/changes/<name>/` printed by an agent. Not in the known set and
    // never will be: the listing carries files, so every directory an agent
    // named was plain text until now.
    expect(desktopReference('openspec/changes/mobil-nezet-reszponziv/', root))
      .toBe('/home/x/proj/openspec/changes/mobil-nezet-reszponziv')
    expect(desktopReference('docs/', root)).toBe('/home/x/proj/docs')
    expect(desktopReference('./openspec/changes/x/', root)).toBe('/home/x/proj/openspec/changes/x')
  })

  it('resolves a relative FILE the project listing does not have', () => {
    // A gitignored file, or one past the listing's cap. `fileReference` answers
    // null for it, so it arrives here rather than staying text.
    expect(desktopReference('build/out/report.html', root))
      .toBe('/home/x/proj/build/out/report.html')
    expect(desktopReference('build/out/report.html:12', root))
      .toBe('/home/x/proj/build/out/report.html')
  })

  it('refuses a relative token when no project root is known', () => {
    // There is nothing to resolve against, and resolving against a working
    // directory the reader cannot see would open a stranger's file of that name.
    expect(desktopReference('openspec/changes/x/')).toBeNull()
  })

  it('does not turn prose into a link just because it has a slash', () => {
    // The filter that replaces the known-file set. Each of these has appeared in
    // this repository's own terminals.
    expect(desktopReference('és/vagy', root)).toBeNull()
    expect(desktopReference('and/or', root)).toBeNull()
    expect(desktopReference('24/7', root)).toBeNull()
    expect(desktopReference('TCP/IP', root)).toBeNull()
  })

  it('refuses a bare word, a clock, and an empty token', () => {
    expect(desktopReference('app.ts', root)).toBeNull()
    expect(desktopReference('12:30', root)).toBeNull()
    expect(desktopReference('', root)).toBeNull()
    expect(desktopReference('   ', root)).toBeNull()
    expect(desktopReference('/', root)).toBeNull()
    // `//host/share` is a UNC-shaped token, not a local path.
    expect(desktopReference('//host/share', root)).toBeNull()
  })
})

/**
 * WHERE THE AGENT IS STANDING — reported 2026-08-26 from a live screen.
 *
 * An agent working in `<project>-wt-<name>` on a change branch printed a
 * relative path, and the dashboard answered `could not open
 * <project>/openspec/changes/<name>: no such file or directory`. It had resolved
 * against the project root — a different checkout, on a different branch.
 *
 * The error is the mild half. The dangerous half has no error at all: when the
 * same relative path exists in BOTH checkouts, the file view opens the main
 * branch's copy, silently, and the reader reads the wrong file believing it is
 * the agent's. Every test below exists to hold one of those two apart.
 */
describe('where a terminal token should be opened', () => {
  const root = '/home/x/proj'
  const wt = '/home/x/proj-wt-mobil'
  // The listing of the checkout the agent is standing in — that substitution is
  // the whole design, so every case below passes the worktree's own listing when
  // the agent is in a worktree.
  const known = new Set(['src/app.ts', 'openspec/changes/a/spec.md'])

  it('opens a worktree file in the file view, and says WHICH checkout', () => {
    // The reported case, and its repair: the internal editor is still the
    // destination — it just reads the tree the agent is standing in.
    expect(terminalTarget('openspec/changes/a/spec.md', { root, cwd: wt, known }))
      .toEqual({ kind: 'file', ref: { path: 'openspec/changes/a/spec.md' }, root: wt })
    expect(terminalTarget('src/app.ts:12', { root, cwd: wt, known }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts', line: 12 }, root: wt })
  })

  it('never answers with the project root for a worktree agent', () => {
    // The silent half of the defect: `src/app.ts` exists in BOTH checkouts, so
    // an answer of `root` would open a different file with the same name.
    const target = terminalTarget('src/app.ts', { root, cwd: wt, known })
    expect(target).not.toBeNull()
    expect(target!.kind === 'file' && target!.root).toBe(wt)
  })

  it('hands a DIRECTORY to the desktop, resolved against the same checkout', () => {
    // No listing contains a directory, so the file view is not a destination.
    expect(terminalTarget('openspec/changes/a/', { root, cwd: wt, known }))
      .toEqual({ kind: 'desktop', path: '/home/x/proj-wt-mobil/openspec/changes/a' })
  })

  it('opens a project file in the file view when the agent stands in the project', () => {
    expect(terminalTarget('src/app.ts', { root, cwd: root, known }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root })
    // And with no cwd reported at all — an older payload — the root is the base.
    expect(terminalTarget('src/app.ts', { root, known }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root })
  })

  it('hands over a path of ANOTHER checkout, which the panel could not read', () => {
    // An absolute path into the main tree, printed by a worktree agent. The
    // file view reads one checkout at a time and this is not that one, so the
    // desktop opens it — with the right content, which is the point.
    expect(terminalTarget('/home/x/proj/src/app.ts', { root, cwd: wt, known }))
      .toEqual({ kind: 'desktop', path: '/home/x/proj/src/app.ts' })
  })

  it('hands over an in-project path the listing does not have', () => {
    expect(terminalTarget('/home/x/proj/openspec/changes/a/', { root, cwd: root, known }))
      .toEqual({ kind: 'desktop', path: '/home/x/proj/openspec/changes/a' })
  })

  it('hands over an absolute path outside the project', () => {
    expect(terminalTarget('/tmp/shot.png', { root, cwd: root, known }))
      .toEqual({ kind: 'desktop', path: '/tmp/shot.png' })
  })

  it('offers an absolute path with no project context, and refuses a relative one', () => {
    expect(terminalTarget('/tmp/shot.png', {})).toEqual({ kind: 'desktop', path: '/tmp/shot.png' })
    expect(terminalTarget('openspec/changes/a/', {})).toBeNull()
  })

  it('leaves prose alone wherever the agent stands', () => {
    expect(terminalTarget('és/vagy', { root, cwd: wt, known })).toBeNull()
    expect(terminalTarget('24/7', { root, cwd: root, known })).toBeNull()
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

describe('the structure carries what is not committed', () => {
  it('attaches a file its own code and nothing to a clean one', () => {
    const tree = buildTree(['src/a.ts', 'src/b.ts'], { 'src/a.ts': ' M' })
    const src = tree[0]
    expect(src.children!.find(n => n.name === 'a.ts')!.status).toBe(' M')
    expect(src.children!.find(n => n.name === 'b.ts')!.status).toBeUndefined()
  })

  it('rolls a change up through every directory above it', () => {
    // The reported case, and the reason the roll-up exists: the folders are
    // collapsed, so a mark only on the file is a mark nobody can see.
    const tree = buildTree(['a/b/c/deep.ts', 'other.md'], { 'a/b/c/deep.ts': ' M' })
    const a = tree.find(n => n.name === 'a')!
    const b = a.children![0]
    const c = b.children![0]
    expect(a.below).toEqual({ changed: true, untracked: false })
    expect(b.below).toEqual({ changed: true, untracked: false })
    expect(c.below).toEqual({ changed: true, untracked: false })
    expect(tree.find(n => n.name === 'other.md')!.below).toBeUndefined()
  })

  it('keeps untracked distinguishable from changed, all the way up', () => {
    const tree = buildTree(['a/new.ts', 'a/edited.ts'],
                           { 'a/new.ts': '??', 'a/edited.ts': 'M ' })
    expect(tree[0].below).toEqual({ changed: true, untracked: true })
  })

  it('marks nothing when there is no status, and nothing when all is clean', () => {
    // These two produce the SAME tree, and that is stated rather than asserted
    // away: at this level "there was nothing to ask" and "I asked and everything
    // is clean" both mean no marks. Measured by mutation — replacing the
    // `if (status)` guard with `status ?? {}` changes no test here, because
    // there is nothing at this level for it to change.
    //
    // So the distinction the endpoint is careful to preserve (`null` vs `{}`)
    // is NOT kept honest here. It is kept honest in the panel, which states the
    // absence in words rather than leaving unmarked rows to imply calm — see
    // `FleetFileView`'s note in the structure pane and its component test.
    const unknown = buildTree(['a/b.ts'])
    const clean = buildTree(['a/b.ts'], {})
    expect(unknown[0].below).toBeUndefined()
    expect(unknown[0].children![0].status).toBeUndefined()
    expect(clean[0].below).toBeUndefined()
  })

  it('calls a directory ignored only when everything under it is', () => {
    const all = buildTree(['.set/x.json', '.set/y.json'],
                          { '.set/x.json': '!!', '.set/y.json': '!!' })
    expect(all[0].ignored).toBe(true)
    // One ignored file beside a tracked one is not an ignored folder: dimming
    // it would hide a file the reader never asked to hide.
    const some = buildTree(['mix/x.json', 'mix/keep.ts'], { 'mix/x.json': '!!' })
    expect(some[0].ignored).toBeUndefined()
  })

  it('does not count an ignored file as work in progress', () => {
    const tree = buildTree(['.set/x.json'], { '.set/x.json': '!!' })
    expect(tree[0].below).toBeUndefined()
  })
})

describe('statusKind reduces a git code to what the tree draws', () => {
  it('names the three cases and leaves clean undefined', () => {
    expect(statusKind('??')).toBe('untracked')
    expect(statusKind('!!')).toBe('ignored')
    expect(statusKind(' M')).toBe('changed')
    expect(statusKind('R ')).toBe('changed')
    expect(statusKind('A ')).toBe('changed')
    expect(statusKind(undefined)).toBeUndefined()
    expect(statusKind('')).toBeUndefined()
  })
})

describe('ancestorsOf, for revealing the open file', () => {
  it('lists every directory between the root and the file, outermost first', () => {
    expect(ancestorsOf('a/b/c.ts')).toEqual(['a', 'a/b'])
  })

  it('gives a top-level file no ancestors', () => {
    // Not `['']` — an empty path would be expanded as a directory that is not
    // there, which is a phantom row in a `Set` nobody can clear.
    expect(ancestorsOf('README.md')).toEqual([])
  })

  it('is not confused by a leading or doubled slash', () => {
    expect(ancestorsOf('/a//b/c.ts')).toEqual(['a', 'a/b'])
  })
})
