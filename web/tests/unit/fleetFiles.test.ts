/**
 * The three decisions the file view rests on, measured without a browser.
 *
 * `fileReference` gets most of the attention because it is the one fed by text
 * somebody else wrote: everything in a terminal was produced by whatever the
 * agent ran, so what this function is willing to call a path is a boundary, not
 * a convenience.
 */
import { describe, expect, it } from 'vitest'

import {
  ancestorsOf, buildListingIndex, buildTree, desktopReference, fileReference, languageOf,
  fileToOpen, RECOGNISER_LIMITS, statusKind, terminalReferences, terminalTarget,
} from '../../src/lib/fleetFiles'

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
  const other = '/home/x/other'
  // The listing of the checkout the agent is standing in — that substitution is
  // the whole design, so every case below passes the worktree's own listing when
  // the agent is in a worktree.
  const paths = ['src/app.ts', 'openspec/changes/a/spec.md', 'src/app/items/[id]/page.tsx']
  const known = new Set(paths)
  const listing = buildListingIndex(paths)
  const checkouts = [root, wt, other]

  it('opens a worktree file in the file view, and says WHICH checkout', () => {
    // The reported case, and its repair: the internal editor is still the
    // destination — it just reads the tree the agent is standing in.
    expect(terminalTarget('openspec/changes/a/spec.md', { root, cwd: wt, known }))
      .toEqual({ kind: 'file', ref: { path: 'openspec/changes/a/spec.md' }, root: wt, confidence: 'high' })
    expect(terminalTarget('src/app.ts:12', { root, cwd: wt, known }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts', line: 12 }, root: wt, confidence: 'high' })
  })

  it('never answers with the project root for a worktree agent', () => {
    // The silent half of the defect: `src/app.ts` exists in BOTH checkouts, so
    // an answer of `root` would open a different file with the same name.
    const target = terminalTarget('src/app.ts', { root, cwd: wt, known })
    expect(target).not.toBeNull()
    expect(target!.kind === 'file' && target!.root).toBe(wt)
  })

  it('reveals a DIRECTORY in the panel rather than launching a file manager', () => {
    // AC-25. No listing carries a directory as an entry, which is why every
    // directory an agent printed used to be plain text or a desktop hand-over.
    expect(terminalTarget('openspec/changes/a/', { root, cwd: wt, listing }))
      .toEqual({ kind: 'directory', path: 'openspec/changes/a', root: wt, confidence: 'high' })
    expect(terminalTarget('openspec/changes/a', { root, cwd: wt, listing }))
      .toEqual({ kind: 'directory', path: 'openspec/changes/a', root: wt, confidence: 'high' })
  })

  it('opens a project file in the file view when the agent stands in the project', () => {
    expect(terminalTarget('src/app.ts', { root, cwd: root, known }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root, confidence: 'high' })
    // And with no cwd reported at all — an older payload — the root is the base.
    expect(terminalTarget('src/app.ts', { root, known }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root, confidence: 'high' })
  })

  it('opens a file of ANOTHER checkout in the panel, naming that checkout', () => {
    // AC-15 — the behaviour this change reverses. An absolute path into the
    // main tree, printed by a worktree agent: the framework may READ it, so the
    // framework opens it, and the answer carries which checkout it meant.
    expect(terminalTarget('/home/x/proj/src/app.ts', { root, cwd: wt, listing, checkouts }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root, confidence: 'high' })
    // AC-16 — and a second registered project is the same case.
    expect(terminalTarget('/home/x/other/lib/x.py', { root, cwd: wt, listing, checkouts }))
      .toEqual({ kind: 'file', ref: { path: 'lib/x.py' }, root: other, confidence: 'high' })
  })

  it('is not fooled by a checkout whose name merely starts the same', () => {
    // A worktree is exactly the string that looks like a sibling of its project,
    // so the boundary test and the longest match are what keep them apart.
    expect(terminalTarget('/home/x/proj-wt-mobil/src/app.ts', { root, cwd: root, listing, checkouts }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root: wt, confidence: 'high' })
    expect(terminalTarget('/home/x/projector/src/app.ts', { root, cwd: root, listing, checkouts }))
      .toEqual({ kind: 'desktop', path: '/home/x/projector/src/app.ts', confidence: 'high' })
  })

  it('still opens an in-project path the listing does not have', () => {
    // The listing is not the boundary — the ENDPOINT is. A file under a checkout
    // the endpoints serve is theirs to refuse or serve, and routing it to the
    // desktop instead means a gitignored but perfectly readable file (a build
    // output, a `.env`) can only be opened by launching something.
    expect(terminalTarget('/home/x/proj/node_modules/pkg/index.js',
                          { root, cwd: root, listing, checkouts }))
      .toEqual({ kind: 'file', ref: { path: 'node_modules/pkg/index.js' }, root, confidence: 'high' })
  })

  it('hands over an absolute path outside the project', () => {
    expect(terminalTarget('/tmp/shot.png', { root, cwd: root, known }))
      .toEqual({ kind: 'desktop', path: '/tmp/shot.png', confidence: 'high' })
  })

  it('offers an absolute path with no project context, and refuses a relative one', () => {
    expect(terminalTarget('/tmp/shot.png', {}))
      .toEqual({ kind: 'desktop', path: '/tmp/shot.png', confidence: 'high' })
    expect(terminalTarget('openspec/changes/a/', {})).toBeNull()
  })

  it('leaves prose alone wherever the agent stands', () => {
    expect(terminalTarget('és/vagy', { root, cwd: wt, known })).toBeNull()
    expect(terminalTarget('24/7', { root, cwd: root, known })).toBeNull()
  })
})

/**
 * THE CONFIDENCE TIER — the repair for 1 464 measured occurrences of an
 * underline that answers *no such file or directory* when it is activated.
 *
 * The fail direction is what makes this normative rather than cosmetic: an
 * underline that fails teaches the reader to distrust every underline on the
 * screen, which spends the credibility of the links that do work. And the tier
 * exists rather than a plain refusal because dropping the token loses `/tmp`
 * and `~/bin/mytool`, which are real paths somebody may want.
 */
describe('how sure the recogniser is', () => {
  const root = '/home/x/proj'
  const known = new Set(['src/app.ts'])

  it('draws nothing for a slash command or a web route', () => {
    // AC-4. Two segments and no extension is not enough to underline.
    for (const token of ['/opsx:ff', '/dd', '/api/v1/items', '/tmp']) {
      const target = terminalTarget(token, { root, cwd: root, known })
      expect(target === null || target.confidence === 'low').toBe(true)
    }
  })

  it('keeps an extensionless path outside every checkout REACHABLE', () => {
    // AC-47 — the half a plain refusal would have lost.
    expect(terminalTarget('/tmp', { root, cwd: root, known }))
      .toEqual({ kind: 'desktop', path: '/tmp', confidence: 'low' })
    expect(terminalTarget('~/bin/mytool', { root, cwd: root, known, home: '/home/x' }))
      .toEqual({ kind: 'desktop', path: '/home/x/bin/mytool', confidence: 'low' })
  })

  it('underlines an outside path that names a file', () => {
    expect(terminalTarget('/tmp/run-4/shot.png', { root, cwd: root, known })?.confidence)
      .toBe('high')
  })

  it('refuses a route parameter at ANY confidence', () => {
    // AC-48. A token carrying brackets is not path-shaped here, so no modifier
    // makes it a link.
    expect(terminalTarget('/items/[id]', { root, cwd: root, known })).toBeNull()
    expect(terminalTarget('/items/<id>', { root, cwd: root, known })).toBeNull()
  })

  it('opens a bracketed path the listing HAS — proof beats shape', () => {
    // The other side of the rule above, and the reason it is stated as a rule:
    // a Next.js dynamic route file carries brackets in its real name.
    const listing = buildListingIndex(['src/app/items/[id]/page.tsx'])
    expect(terminalTarget('src/app/items/[id]/page.tsx', { root, cwd: root, listing }))
      .toEqual({
        kind: 'file', ref: { path: 'src/app/items/[id]/page.tsx' }, root, confidence: 'high',
      })
  })
})

/**
 * WHAT AN AGENT ACTUALLY WRITES AROUND A PATH.
 *
 * Measured over 30 session transcripts: of 249 distinct tokens naming a file
 * that exists and left as plain text, 121 were lost to leftover markup alone.
 */
describe('the punctuation around a path', () => {
  const root = '/home/x/proj'
  const paths = ['docs/x.md', 'src/app.ts', 'src/lib/util.ts', 'test/lib/util.ts']
  const listing = buildListingIndex(paths)
  const where = { root, cwd: root, listing }

  it('reads a path through markdown emphasis, backticks, or both', () => {
    // AC-5
    for (const token of ['**docs/x.md**', '`docs/x.md`', '**`docs/x.md`**', '`docs/x.md`**']) {
      expect(terminalTarget(token, where))
        .toEqual({ kind: 'file', ref: { path: 'docs/x.md' }, root, confidence: 'high' })
    }
  })

  it('reads a path out of a table cell, keeping the line number', () => {
    // AC-6 — the separator is punctuation, the `:12` is not.
    expect(terminalTarget('docs/x.md:12|', where))
      .toEqual({ kind: 'file', ref: { path: 'docs/x.md', line: 12 }, root, confidence: 'high' })
  })

  it('does not let a sentence full stop name a file that does not exist', () => {
    // Measured: seven working links broke when the first candidate placed
    // through the SHAPE rule while a later candidate was in the listing.
    expect(terminalTarget('src/app.ts.', where))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root, confidence: 'high' })
  })

  it('does not let an over-stripped candidate name a directory', () => {
    // A Next.js dynamic-route directory ends in `]`, which is also what a
    // sentence leaves on a path. Stripping is right for the prose and wrong
    // here, so every candidate is offered to the listing BEFORE any of them is
    // allowed to place on its shape alone.
    const routes = buildListingIndex(['src/app/items/[id]/page.tsx'])
    expect(terminalTarget('src/app/items/[id]', { root, cwd: root, listing: routes }))
      .toEqual({ kind: 'directory', path: 'src/app/items/[id]', root, confidence: 'high' })
  })

  it('drops the punctuation when NOTHING in the listing can settle it', () => {
    // `<checkout>/.venv/bin/python:` — a real file the listing excludes, so no
    // candidate can be proven. Measured: the trailing colon survived into the
    // answer and the reference named nothing.
    expect(terminalTarget('/home/x/proj/.venv/bin/python:',
                          { root, cwd: root, listing, checkouts: [root] }))
      .toEqual({ kind: 'file', ref: { path: '.venv/bin/python' }, root, confidence: 'high' })
  })

  it('refuses a glob, whose star is the thing that says it names no one file', () => {
    expect(terminalTarget('`docs/inputs/2026-08-25-*`', where)).toBeNull()
    expect(terminalTarget('src/**/*.ts', where)).toBeNull()
  })

  it('expands a home-relative token against the framework account', () => {
    // AC-7 — and refuses it outright when no home was supplied, because the
    // browser guessing a home links to a file belonging to somebody else.
    expect(terminalTarget('~/proj/src/app.ts', { ...where, home: '/home/x', checkouts: [root] }))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root, confidence: 'high' })
    expect(terminalTarget('~/proj/src/app.ts', where)).toBeNull()
  })

  it('resolves a token that is a unique SUFFIX of one known file', () => {
    // AC-8
    expect(terminalTarget('src/lib/util.ts', where))
      .toEqual({ kind: 'file', ref: { path: 'src/lib/util.ts' }, root, confidence: 'high' })
    expect(terminalTarget('app.ts', where))
      .toEqual({ kind: 'file', ref: { path: 'src/app.ts' }, root, confidence: 'high' })
  })

  it('offers the matches when a token suffixes SEVERAL known files', () => {
    // AC-9 — never picks one. A wrong file that opens looks exactly like a
    // right one, and nothing on the screen says otherwise.
    expect(terminalTarget('lib/util.ts', where)).toEqual({
      kind: 'choice',
      matches: [{ path: 'src/lib/util.ts' }, { path: 'test/lib/util.ts' }],
      root,
      confidence: 'high',
    })
  })

  it('matches a suffix only on a path boundary', () => {
    // `actions/dashboard.ts` must NOT resolve to `.../my-actions/dashboard.ts`.
    // It still becomes a reference — the endpoint is what answers whether that
    // file is there — but it must never name the wrong file, because a wrong
    // file that opens looks exactly like a right one.
    const other = buildListingIndex(['src/my-actions/dashboard.ts'])
    expect(terminalTarget('actions/dashboard.ts', { root, cwd: root, listing: other }))
      .toEqual({
        kind: 'file', ref: { path: 'actions/dashboard.ts' }, root, confidence: 'high',
      })
  })

  it('resolves a climbing relative token instead of naming nothing', () => {
    // `'../lib/fleetFiles'` is an import specifier, and `<base>/../lib/...` is a
    // string that names no file — every consumer of the answer compares strings.
    expect(terminalTarget("'../lib/x.ts'", { root: '/home/x/proj', cwd: '/home/x/proj/web', known: new Set() }))
      .toEqual({ kind: 'desktop', path: '/home/x/proj/lib/x.ts', confidence: 'high' })
  })
})

/**
 * THE LIMITS — a bound nothing can test is a bound nobody will notice going
 * wrong. An unbounded scan degrades exactly while an agent is producing output
 * fastest, and a stuttering terminal is indistinguishable from a stalled agent.
 */
describe('what the recogniser refuses to spend', () => {
  const root = '/home/x/proj'
  const known = new Set(['src/app.ts'])
  const where = { root, cwd: root, known }

  it('finds the references on an ordinary row', () => {
    const found = terminalReferences('see src/app.ts:12 and /tmp/shot.png now', where)
    expect(found.map(r => r.token)).toEqual(['src/app.ts:12', '/tmp/shot.png'])
    expect(found[0].index).toBe(4)
  })

  it('does not scan a row past the length limit AT ALL', () => {
    // AC-49. Not scanned partly: a partial scan produces links whose columns are
    // right and whose coverage is arbitrary, which is worse than none.
    const row = 'x'.repeat(RECOGNISER_LIMITS.row) + ' src/app.ts'
    expect(terminalReferences(row, where)).toEqual([])
  })

  it('stops after the reference limit for one row', () => {
    const row = Array.from({ length: 30 }, () => '/tmp/shot.png').join(' ')
    expect(terminalReferences(row, where).length).toBe(RECOGNISER_LIMITS.perRow)
  })

  it('skips a token longer than the token limit', () => {
    const long = '/tmp/' + 'a'.repeat(RECOGNISER_LIMITS.token) + '.png'
    expect(terminalReferences(long + ' src/app.ts', where).map(r => r.token))
      .toEqual(['src/app.ts'])
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
