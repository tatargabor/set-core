/**
 * The decisions behind the file view, kept out of the component so they can be
 * measured without a browser.
 *
 * Three of them are here, and each is a place where being *nearly* right is
 * indistinguishable from being right until it matters:
 *
 *  - what a flat list of paths becomes on screen (`buildTree`),
 *  - what a path is called in Monaco's language (`languageOf`),
 *  - where a token in terminal output should be OPENED (`terminalTarget`),
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
  /**
   * Git's own two-character code for this FILE, when it is not clean — ` M`,
   * `??`, `R `, and `!!` for an entry present only because ignored files were
   * asked for. Absent means clean, which is the same convention the endpoint
   * uses: one representation of clean is enough.
   */
  status?: string
  /**
   * For a DIRECTORY: what lies anywhere beneath it. A summary and never a code,
   * because a directory does not have one — inventing a `M ` for a folder would
   * be a false value sitting next to real ones.
   *
   * This is what makes a collapsed folder honest. Every layout that hides
   * something creates a place a changed thing can sit while the screen looks
   * settled (`ui-quality`), so what is hidden and wrong is marked where the
   * reader is standing, not only where it lives.
   */
  below?: { changed: boolean; untracked: boolean }
  /** Whether everything here is ignored — the whole row renders subordinate. */
  ignored?: boolean
}

/** What a git status code MEANS to this screen. */
export type StatusKind = 'untracked' | 'ignored' | 'changed'

/**
 * A two-character git code, reduced to the three cases the tree draws.
 *
 * Three and not more on purpose. The full porcelain vocabulary distinguishes
 * index from working tree, and a reader of a file TREE cannot act on that
 * distinction — they can act on *this was never committed*, *this has work in
 * it*, and *this is only here because I asked for ignored files*. The exact code
 * stays on the node for the row's title, so nothing is lost, only summarised.
 */
export function statusKind(code: string | undefined): StatusKind | undefined {
  if (!code) return undefined
  if (code === '!!') return 'ignored'
  if (code === '??') return 'untracked'
  return 'changed'
}

/**
 * Every directory between the root and a path, outermost first.
 *
 * `a/b/c.ts` → `['a', 'a/b']`. The file itself is not one of its own ancestors,
 * and a top-level file has none. Used to reveal the open file: a mark on a row
 * that is not rendered is a mark nobody can see.
 */
export function ancestorsOf(path: string): string[] {
  const parts = path.split('/').filter(Boolean)
  parts.pop()
  return parts.map((_, i) => parts.slice(0, i + 1).join('/'))
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
 *
 * ## `status`, and why the roll-up happens HERE
 *
 * The optional second argument is the endpoint's map of non-clean paths. Passing
 * it attaches each file's code to its node AND summarises every directory by
 * what lies beneath it, at any depth, in the same single pass.
 *
 * This is the only place that sees a directory together with its whole subtree.
 * Rolling up in the row component instead would walk the subtree once per
 * directory per render, and would put a decision about MEANING inside something
 * whose job is drawing.
 *
 * `undefined` and `{}` are different arguments and must stay so: no map means
 * the listing had nothing to report — no repository — and the tree then carries
 * no marks and makes no claim. An empty map means everything is clean. A tree
 * that rendered both the same way would report calm it never measured.
 */
export function buildTree(
  paths: readonly string[],
  status?: Readonly<Record<string, string>> | null,
): TreeNode[] {
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
  sort(root)
  if (status) decorate(root, status)
  return root.children ?? []
}

/**
 * Attach each file's code, then summarise every directory by its subtree.
 *
 * Depth-first and bottom-up, so a directory sees its children already decorated
 * — one pass, and a folder ten levels above a modified file is marked by the
 * same rule as its immediate parent.
 *
 * A directory counts as ignored only when it has children and ALL of them are:
 * a folder holding one ignored file beside three tracked ones is not an ignored
 * folder, and dimming it would hide three files the reader did not ask to hide.
 */
function decorate(node: TreeNode, status: Readonly<Record<string, string>>): void {
  if (!node.dir) {
    const code = status[node.path]
    if (code) {
      node.status = code
      node.ignored = code === '!!'
    }
    return
  }
  const children = node.children ?? []
  children.forEach(child => decorate(child, status))
  const below = { changed: false, untracked: false }
  for (const child of children) {
    const kind = statusKind(child.status)
    if (kind === 'untracked') below.untracked = true
    if (kind === 'changed') below.changed = true
    if (child.below?.untracked) below.untracked = true
    if (child.below?.changed) below.changed = true
  }
  if (below.changed || below.untracked) node.below = below
  if (children.length > 0 && children.every(c => c.ignored)) node.ignored = true
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
 * read nothing. Which of the two answers a given token is `terminalTarget`
 * below — this function does not know about the file view and does not refuse a
 * path because the file view could have opened it.
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
 *  - **a relative token needs a BASE to resolve against.** Without one — a
 *    docked panel with no project — it stays text rather than being resolved
 *    against a working directory the reader cannot see. Which base that is —
 *    the agent's own working directory, not the project root — is
 *    `terminalTarget`'s decision, and the reason it exists.
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
export function desktopReference(token: string, base?: string): string | null {
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

  if (path.startsWith('/')) return path

  const normalisedBase = base?.replace(/\/+$/, '') ?? ''
  if (!normalisedBase) return null
  if (!looksLikePath(written)) return null
  return normalisedBase + '/' + path
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


/** Where a token in terminal output should be opened, or `null` for text. */
export type TerminalTarget =
  /** In the file view — `root` is the CHECKOUT the path is relative to. */
  | { kind: 'file'; ref: FileRef; root: string }
  | { kind: 'desktop'; path: string }
  | null

/**
 * THE ONE PLACE that decides where a terminal token goes.
 *
 * `fileReference` and `desktopReference` each answer "is this token mine?".
 * Neither may answer "which of us wins", because that answer depends on
 * something neither of them holds: WHERE THE AGENT IS STANDING.
 *
 * ## The worktree, which is what this function was written for
 *
 * Reported 2026-08-26 from a live screen: an agent working in
 * `<project>-wt-<name>` on a change branch printed a relative path, and the
 * dashboard answered `could not open <project>/openspec/changes/<name>: no such
 * file or directory` — it had resolved the path against the PROJECT ROOT, which
 * is a different checkout on a different branch.
 *
 * Two ways that goes wrong, and the second is worse than the error the reader
 * actually saw:
 *
 *  - the path does not exist in the main checkout, and the reader gets a
 *    refusal for a file that is plainly in front of the agent;
 *  - **the path DOES exist in both**, and the reader is shown the main branch's
 *    copy — a different file, with the same name, silently. A wrong file that
 *    opens is worse than a right one that refuses.
 *
 * So the BASE for everything here is `cwd` — where the agent stands — and
 * `root` is only the fallback for a payload that reported no cwd.
 *
 * ## Why `known` is the base's listing, and why that is the whole design
 *
 * The caller passes the file listing OF THE BASE. That one substitution is what
 * lets a worktree file open in the internal editor rather than on the desktop:
 * the framework serves a worktree of a known project, so the same
 * `fileReference` answer is right in both checkouts, and the answer now carries
 * WHICH checkout it meant.
 *
 * What is left for the desktop is then exactly what the file view cannot open:
 * a directory (no listing contains one), a file no listing has, and any
 * absolute path outside the base. That is the rule the reader asked for —
 * *anything inside the project that the internal editor can open, opens there*.
 */
export function terminalTarget(
  token: string,
  where: { root?: string; cwd?: string; known?: ReadonlySet<string> },
): TerminalTarget {
  const { root, cwd, known } = where
  const base = cwd || root

  if (base && known && known.size > 0) {
    const ref = fileReference(token, base, known)
    if (ref) return { kind: 'file', ref, root: base }
  }
  const path = desktopReference(token, base)
  return path ? { kind: 'desktop', path } : null
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
