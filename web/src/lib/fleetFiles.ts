/**
 * The decisions behind the file view, kept out of the component so they can be
 * measured without a browser.
 *
 * Three of them are here, and each is a place where being *nearly* right is
 * indistinguishable from being right until it matters:
 *
 *  - what a flat list of paths becomes on screen (`buildTree`),
 *  - what a path is called in Monaco's language (`languageOf`),
 *  - and what counts as a file reference in an agent's terminal output
 *    (`fileReference`, and `desktopReference` for the paths the file view cannot
 *    open) — the ones fed by text somebody else wrote.
 */

/** One node of the structure. A directory holds children; a file does not. */
export interface TreeNode {
  name: string
  path: string
  dir: boolean
  children?: TreeNode[]
}

/**
 * A flat list of paths, as the endpoint returns it, becomes the tree on screen.
 *
 * Built here rather than on the server on purpose: one request instead of one
 * per expanded directory, no server-side memory of what is open, and the cap
 * stays a single number in a single place.
 *
 * Directories sort before files and both sort by name — a listing whose order
 * changes between renders is a listing nobody can find anything in twice.
 */
export function buildTree(paths: readonly string[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', dir: true, children: [] }
  for (const p of paths) {
    const parts = p.split('/').filter(Boolean)
    let node = root
    parts.forEach((part, i) => {
      const last = i === parts.length - 1
      const path = parts.slice(0, i + 1).join('/')
      let next = node.children?.find(c => c.name === part && c.dir === !last)
      if (!next) {
        next = { name: part, path, dir: !last, ...(last ? {} : { children: [] }) }
        node.children!.push(next)
      }
      node = next
    })
  }
  const sort = (n: TreeNode): TreeNode => {
    if (!n.children) return n
    n.children.sort((a, b) => (a.dir === b.dir ? a.name.localeCompare(b.name) : a.dir ? -1 : 1))
    n.children.forEach(sort)
    return n
  }
  return sort(root).children ?? []
}

/**
 * Monaco's name for a file's language, or `undefined` for "no colours".
 *
 * `undefined` is a real answer and not a failure: an unknown extension gets a
 * plain-text file, never a file that refuses to open. That is the difference
 * between compacting and hiding, applied to syntax.
 *
 * The map is deliberately short. A long one is a second copy of Monaco's own
 * registry, and it drifts the day Monaco learns a language.
 */
const LANGUAGES: Record<string, string> = {
  ts: 'typescript', tsx: 'typescript', mts: 'typescript', cts: 'typescript',
  js: 'javascript', jsx: 'javascript', mjs: 'javascript', cjs: 'javascript',
  py: 'python', rb: 'ruby', go: 'go', rs: 'rust', java: 'java', kt: 'kotlin',
  php: 'php', cs: 'csharp', c: 'c', h: 'c', cpp: 'cpp', hpp: 'cpp', cc: 'cpp',
  css: 'css', scss: 'scss', less: 'less', html: 'html', xml: 'xml', svg: 'xml',
  json: 'json', yaml: 'yaml', yml: 'yaml', toml: 'ini', ini: 'ini',
  md: 'markdown', sh: 'shell', bash: 'shell', zsh: 'shell', sql: 'sql',
  dockerfile: 'dockerfile', prisma: 'prisma', graphql: 'graphql',
}

export function languageOf(path: string): string | undefined {
  const name = path.split('/').pop() ?? ''
  if (name.toLowerCase() === 'dockerfile') return 'dockerfile'
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : ''
  return LANGUAGES[ext]
}

/** A reference found in terminal output: which file, and optionally which line. */
export interface FileRef {
  path: string
  line?: number
}

/**
 * The punctuation a sentence leaves around a path, removed.
 *
 * Leading first, then trailing — and a trailing `:<digits>` is NOT punctuation,
 * it is the line number, which is the whole reason the trailing strip is a
 * callback and not a plain replace.
 *
 * Shared by both recognisers below rather than written twice: the reported case
 * was `(/tmp/…/screenshot-2.jpg)`, so a second copy that forgot one bracket
 * would produce a link that is underlined and wrong, which is worse than none.
 */
function unwrap(token: string): string {
  const text = token.trim().replace(/^[([<'"`]+/, '')
  return text.replace(/[)\]>,.;:'"`]+$/, m => (/^:\d+$/.test(m) ? m : ''))
}

/**
 * Whether a token from an agent's terminal is a reference to a file of THIS
 * project — and if so, which file and which line.
 *
 * ## The text is data, not an instruction
 *
 * Everything in a terminal was written by whatever the agent ran, so this
 * function is the boundary: it decides what the dashboard is willing to treat as
 * a path at all. Two rules follow, and both are refusals:
 *
 *  - **an absolute path is a reference only if it is inside this project's
 *    root.** `/etc/shadow` printed by an agent is text.
 *  - **a relative path must be one the project actually has.** The caller passes
 *    the set of known paths — the listing it already fetched — so a sentence
 *    containing `a.b` or `12:30` cannot become a link to something that does not
 *    exist. Guessing would produce links that 404 on click, and a control that
 *    fails on click is worse than no control.
 *
 * The `path:line` shape is the one this repository's own tools print, and the
 * colon is the ambiguity worth naming: it separates a line number here and is
 * ordinary text elsewhere (`http://`, `12:30:05`). Resolved by requiring digits
 * to the end of the token, and by checking the path part against the known set
 * BEFORE the split is believed.
 */
export function fileReference(
  token: string,
  root: string,
  known: ReadonlySet<string>,
): FileRef | null {
  const text = unwrap(token)
  if (!text) return null

  const withLine = /^(.*?):(\d+)(?::\d+)?$/.exec(text)
  const candidates: Array<{ path: string; line?: number }> = []
  if (withLine) candidates.push({ path: withLine[1], line: Number(withLine[2]) })
  candidates.push({ path: text })

  const normalisedRoot = root.replace(/\/+$/, '')
  for (const c of candidates) {
    let rel = c.path
    if (!rel) continue
    if (rel.startsWith('/')) {
      // Absolute: only inside this project, and compared on a path boundary so
      // that `/home/x/proj-other` is not read as inside `/home/x/proj`.
      if (rel !== normalisedRoot && !rel.startsWith(normalisedRoot + '/')) continue
      rel = rel.slice(normalisedRoot.length + 1)
    }
    rel = rel.replace(/^\.\//, '')
    if (!rel || !known.has(rel)) continue
    return c.line === undefined ? { path: rel } : { path: rel, line: c.line }
  }
  return null
}

/**
 * The absolute path a terminal token names, for the route that hands a path to
 * the DESKTOP — or `null` when the token is not one.
 *
 * The complement of `fileReference`, and deliberately its own function rather
 * than a widened version of it, because the two answer different questions and
 * end in different places: one names a file the framework may READ and open in
 * the file view; this one names a path the framework may only HAND OVER, having
 * read nothing. `fileReference` is asked first, so a file the project actually
 * has never reaches here.
 *
 * ## Two kinds of token reach the desktop
 *
 *  - **an absolute path outside the project.** Reported 2026-08-26: an agent
 *    prints where it put a screenshot, and it is almost never inside the tree it
 *    is working in.
 *  - **a relative path the project does not have as a FILE.** Reported the same
 *    day, with `openspec/changes/<name>/` as the case — a DIRECTORY. The file
 *    listing carries files, so no directory is ever in the known set, and every
 *    directory an agent printed was therefore plain text.
 *
 * ## The rules, and why each one is a refusal
 *
 *  - **no `://`.** A URL is the other link provider's business, and handing one
 *    to a desktop opener is how a `file:` or a `javascript:` scheme gets a
 *    second chance at being followed.
 *  - **a trailing `:<line>` is dropped.** A desktop handler takes no line
 *    number, and `/tmp/run.log:42` should still open `/tmp/run.log` rather than
 *    fail as a path that does not exist.
 *  - **an absolute path inside the known root wins the other way.** The file
 *    view is the right destination there. Precedence lives in this one place on
 *    purpose: two link providers deciding it by their registration order is a
 *    rule nobody can read off the code.
 *  - **a relative token needs a root to resolve against.** Without one — a
 *    docked panel with no project — it stays text rather than being resolved
 *    against a working directory the reader cannot see.
 *  - **and a relative token must LOOK like a path**, which is the load-bearing
 *    one. `fileReference` keeps prose out by checking the known set; this route
 *    has no such set, so the shape is the only filter left. See `looksLikePath`.
 *
 * What it does NOT check is whether the path exists, and that is a decision, not
 * an omission. Asking the server would answer "is there a file at X" for any
 * path on the machine, one request at a time — the oracle the file endpoints
 * refuse to be. The cost is accepted and paid where the reader is standing: an
 * activation that cannot be honoured reports its reason.
 */
export function desktopReference(token: string, root?: string): string | null {
  const text = unwrap(token)
  if (!text) return null
  if (text.includes('://')) return null
  if (text.startsWith('//')) return null

  // Same `path:line` shape as `fileReference` reads, minus the line: this
  // destination has nowhere to put it.
  const withoutLine = /^(.*?):(\d+)(?::\d+)?$/.exec(text)?.[1] ?? text
  const written = withoutLine.replace(/^\.\//, '')
  // A trailing slash is how a directory is usually printed. It is dropped from
  // the ANSWER so the message names the directory rather than the directory plus
  // a slash — but the shape test below sees the token as it was written, because
  // that slash is one of the three things that make a token look like a path.
  const path = written.replace(/(.)\/+$/, '$1')
  if (path.length < 2) return null

  const normalisedRoot = root?.replace(/\/+$/, '') ?? ''

  if (path.startsWith('/')) {
    // Path-boundary comparison, so `/home/x/proj-other` is not read as inside
    // `/home/x/proj` — the same boundary `fileReference` draws, in reverse.
    if (normalisedRoot && (path === normalisedRoot || path.startsWith(normalisedRoot + '/'))) {
      return null
    }
    return path
  }

  if (!normalisedRoot) return null
  if (!looksLikePath(written)) return null
  return normalisedRoot + '/' + path
}

/**
 * Whether a relative token is shaped like a path at all.
 *
 * This is the filter that replaces `fileReference`'s known-file set, and it
 * exists because of what a terminal actually contains: prose. An agent writes
 * sentences, and a rule as simple as "contains a slash" turns `és/vagy`,
 * `and/or`, `24/7` and `TCP/IP` into links that fail when clicked.
 *
 * Three conditions, chosen so the misses fall in the harmless direction:
 *
 *  - **ASCII path characters only.** Accented prose is excluded; a real path
 *    with an accent in it is missed. A missed link costs a right-click; a wrong
 *    one costs the reader's trust in every underline on the screen.
 *  - **at least one slash**, because a bare word is a word.
 *  - **and one of: a second slash, a trailing slash, or a dot-extension.** That
 *    is what separates `openspec/changes/x`, `docs/` and `src/app.ts` from
 *    `and/or`.
 *
 * It is given the token AS WRITTEN, trailing slash included, because that slash
 * is one of the three signals. What this misses — `web/src`, one slash, no
 * extension, no trailing slash — is mostly covered already: a relative FILE the
 * project has is `fileReference`'s answer, not this one's.
 */
function looksLikePath(written: string): boolean {
  if (!/^[A-Za-z0-9._+@\-/]+$/.test(written)) return false
  const slashes = (written.match(/\//g) ?? []).length
  if (slashes === 0) return false
  if (slashes >= 2 || written.endsWith('/')) return true
  return /\/[^/]*\.[A-Za-z0-9]+$/.test(written)
}


/**
 * Which file the panel should open when somebody opens the panel.
 *
 * Asked for 2026-08-22 — *"files ha bezarom akkor mentse el hol volt hogy ha
 * ujra kinyitom akkor ott legyen"* — and it is one line of policy that decides
 * two very different behaviours, so it lives here where it can be measured
 * rather than inline in a click handler.
 *
 * The rule and the reason it is asymmetric:
 *
 *  - **an empty path means "just open the panel"** — the control in the project
 *    header, which names no file. That is the ONLY case the remembered file
 *    answers.
 *  - **a named file always wins.** Somebody who ctrl-clicked a path asked for
 *    that path; restoring where they were instead would silently ignore the
 *    click, which is the failure that reads as a broken link.
 *
 * With nothing remembered the request comes back unchanged, so the panel opens
 * on its structure exactly as it did before anything was remembered.
 */
export function fileToOpen(requested: FileRef, remembered?: FileRef | null): FileRef {
  if (requested.path) return requested
  return remembered ?? requested
}
