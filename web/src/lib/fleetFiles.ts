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
 * How sure the recogniser is that a token names a path — and therefore how the
 * link is DRAWN, which is the whole reason the tier exists.
 *
 * Not a binary link-or-text answer, because both halves of that answer are
 * wrong in a measured way. Underlining everything path-shaped produced 1 464
 * occurrences of a link that answers *no such file or directory* when
 * activated, and an underline that fails teaches the reader to distrust every
 * other underline on the screen. Dropping everything unplaceable loses `/tmp`
 * and `~/bin/mytool`, which are real paths somebody may want.
 *
 * So a `low` reference is recognised and reachable, and draws nothing: no
 * underline, no tooltip, activatable only while the modifier is held. The same
 * shape VS Code's terminal settled on for the same problem.
 */
export type Confidence = 'high' | 'low'

/** Where a token in terminal output should be opened, or `null` for text. */
export type TerminalTarget =
  /** In the file view — `root` is the CHECKOUT the path is relative to. */
  | { kind: 'file'; ref: FileRef; root: string; confidence: Confidence }
  /** Revealed in the panel's structure pane. `path` is relative to `root`. */
  | { kind: 'directory'; path: string; root: string; confidence: Confidence }
  /** Several files end with the token — the reader chooses, nothing opens. */
  | { kind: 'choice'; matches: FileRef[]; root: string; confidence: Confidence }
  | { kind: 'desktop'; path: string; confidence: Confidence }
  | null

/**
 * What the recogniser refuses to spend, stated rather than left implicit.
 *
 * Nothing bounded this work before, and the suffix index below makes the
 * unbounded version worse: it would run per token, per rendered row, against a
 * listing of up to 30 121 entries. The numbers are the ones VS Code's terminal
 * link stack carries, because that is a system which has actually hit them.
 *
 * The reason to bound it at all is a failure that looks like a different
 * failure: an unbounded scan degrades exactly when an agent is producing output
 * fastest, and a terminal that stutters while an agent works is
 * indistinguishable from an agent that has stalled.
 */
export const RECOGNISER_LIMITS = {
  /** A row longer than this is not scanned at all. */
  row: 2000,
  /** How many references one row may carry before scanning stops. */
  perRow: 10,
  /** A single token longer than this is skipped. */
  token: 1024,
} as const

/**
 * A checkout's listing, indexed for the three questions the recogniser asks.
 *
 * Built ONCE per listing, not per token: the listing is up to 20 000 paths and
 * the check would otherwise run per token per rendered row. The link provider
 * already re-registers when a listing arrives, so there is a natural place.
 *
 * `dirs` is DERIVED from the file paths and is the reason a directory can be
 * recognised at all — no listing carries a directory as an entry, which is why
 * every directory an agent printed used to be plain text.
 */
export interface ListingIndex {
  /** Every file path the listing carries, relative to the checkout. */
  files: ReadonlySet<string>
  /** Every directory implied by those paths. */
  dirs: ReadonlySet<string>
  /** Last path segment → the paths ending in it, for suffix resolution. */
  tails: ReadonlyMap<string, readonly string[]>
}

export function buildListingIndex(paths: Iterable<string>): ListingIndex {
  const files = new Set<string>()
  const dirs = new Set<string>()
  const tails = new Map<string, string[]>()
  for (const raw of paths) {
    const rel = raw.replace(/^\.\//, '').replace(/^\/+/, '')
    if (!rel) continue
    files.add(rel)
    const parts = rel.split('/')
    for (let i = 1; i < parts.length; i += 1) dirs.add(parts.slice(0, i).join('/'))
    const last = parts[parts.length - 1]
    const bucket = tails.get(last)
    if (bucket) bucket.push(rel)
    else tails.set(last, [rel])
  }
  return { files, dirs, tails }
}

/** The wrapper characters an agent's prose leaves on the two ends of a path. */
const LEADING = new Set(['(', '[', '<', '{', "'", '"', '`', '*', '|'])
const TRAILING = new Set([')', ']', '>', '}', "'", '"', '`', '*', '|', ',', ';', '.', ':'])

/**
 * A token carrying a star may place only through PROOF — never through shape.
 *
 * The star is doing one of two jobs and the token cannot say which: markdown
 * emphasis around a path (`**docs/x.md**`, which the spec requires to work), or
 * a GLOB (`docs/inputs/2026-08-25-*`, which names no single file). Stripping it
 * as a wrapper serves the first and breaks the second — measured: agents print
 * globs constantly, and each one became an underlined link to a file that does
 * not exist, its star quietly removed.
 *
 * The listing settles it and nothing else can. So a starred token is offered to
 * the listing, and where the listing does not have it, it stays text rather
 * than being guessed at from its shape.
 */
function carriesGlob(token: string): boolean {
  return token.includes('*')
}

/**
 * The token as written, then each progressively unwrapped variant of it.
 *
 * A LIST rather than one destructive strip, which is the repair task 1.1 names.
 * One strip has to decide, for the whole token at once, which characters were
 * punctuation — and a wrong guess deletes the variant that would have matched.
 * VS Code's detector generates candidates for the same reason.
 *
 * Ordered least-stripped first, and the caller takes the FIRST that places, so
 * a file whose own name ends in a bracket still wins over the stripped reading
 * of it.
 *
 * A trailing `:<digits>` is never stripped here: it is the line number, and
 * removing it as punctuation is how `docs/x.md:12` loses the 12. A trailing
 * `:` with nothing after it IS punctuation, and a line number cannot end in one.
 */
export function unwrapCandidates(token: string): string[] {
  const out: string[] = []
  const push = (s: string): void => { if (s && !out.includes(s)) out.push(s) }

  let text = token.trim()
  push(text)

  // A markdown link — `[what it is](the/path)`. The path is the tail, and no
  // amount of end-stripping reaches it, so it is offered as its own candidate.
  const md = /\]\(([^)]+)\)$/.exec(text)
  if (md) push(md[1])

  for (let step = 0; step < 12; step += 1) {
    const last = text[text.length - 1]
    if (last !== undefined && TRAILING.has(last)) {
      text = text.slice(0, -1)
    } else if (text.length > 0 && LEADING.has(text[0])) {
      text = text.slice(1)
    } else {
      break
    }
    push(text)
  }
  return out
}

/**
 * The (path, line) readings of one candidate, most specific first.
 *
 * `path:line` is the shape this repository's own tools print, and the colon is
 * the ambiguity worth naming: it separates a line number here and is ordinary
 * text elsewhere (`12:30:05`). Both readings are returned and the caller keeps
 * the first that resolves, so a file whose name genuinely ends `:12` still wins.
 */
function pathAndLine(candidate: string): FileRef[] {
  const withLine = /^(.*?):(\d+)(?::\d+)?$/.exec(candidate)
  const out: FileRef[] = []
  if (withLine && withLine[1]) out.push({ path: withLine[1], line: Number(withLine[2]) })
  out.push({ path: candidate })
  return out
}

/**
 * The longest of `roots` that contains `abs`, on a path boundary — or `null`.
 *
 * Both halves are load-bearing and both have a measured failure behind them.
 * The BOUNDARY is what keeps `/home/u/proj` from swallowing `/home/u/proj-other`
 * — and a worktree is exactly the string that looks like a sibling of its
 * project (`<project>-wt-<name>`). The LONGEST is what keeps a project nested
 * inside another one from being read as a file of the outer one.
 */
function insideCheckout(abs: string, roots: readonly string[]): string | null {
  let best: string | null = null
  for (const raw of roots) {
    const root = raw.replace(/\/+$/, '')
    if (!root) continue
    if (abs !== root && !abs.startsWith(root + '/')) continue
    if (best === null || root.length > best.length) best = root
  }
  return best
}

/**
 * The path characters this recogniser accepts OUTSIDE every served checkout.
 *
 * `#` is here because real files carry it — the agent channel names a room file
 * `<project>#<hash>.md`, and 7 working links were lost to leaving it out.
 * Brackets and angles are deliberately NOT here: `/items/[id]` is a web route,
 * and the spec settles that case as text at any confidence.
 *
 * INSIDE a checkout this test is not applied at all — see `classify`. A path
 * that starts with a checkout the endpoints serve has already produced its
 * evidence, and applying a prose filter on top of it costs real files: a
 * Next.js dynamic-route file is `src/app/items/[id]/page.tsx` in its own tree.
 */
const PATH_CHARS = /^[A-Za-z0-9._+@#\-/]+$/

/**
 * Whether a relative token is shaped like a path at all.
 *
 * This is the filter that replaces a known-file set, and it exists because of
 * what a terminal actually contains: prose. An agent writes sentences, and a
 * rule as simple as "contains a slash" turns `és/vagy`, `and/or`, `24/7` and
 * `TCP/IP` into links that fail when clicked.
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
 * is one of the three signals.
 */
function looksLikePath(written: string): boolean {
  if (!PATH_CHARS.test(written)) return false
  const slashes = (written.match(/\//g) ?? []).length
  if (slashes === 0) return false
  if (slashes >= 2 || written.endsWith('/')) return true
  return /\/[^/]*\.[A-Za-z0-9]+$/.test(written)
}

/** A trailing slash removed, without turning `/` itself into nothing. */
function withoutTrailingSlash(path: string): string {
  return path.replace(/(.)\/+$/, '$1')
}

/**
 * An absolute path with its `.` and `..` segments resolved away.
 *
 * Needed because a relative token is joined to a base, and agents print
 * relative tokens that climb: `'../lib/fleetFiles'` is an import specifier, and
 * `<base>/../lib/fleetFiles` is a string that names nothing. Every consumer of
 * the answer — the prefix test that decides which checkout it is in, the
 * endpoint that confines it — compares STRINGS, so an unnormalised one lands in
 * the wrong checkout or in none.
 *
 * A `..` that climbs past the root is dropped rather than kept: `/..` is `/`
 * on every filesystem this runs on, and keeping it would produce a path the
 * prefix test reads as outside every checkout for a reason that is not true.
 */
function normalise(abs: string): string {
  if (!abs.includes('/.')) return abs
  const out: string[] = []
  for (const part of abs.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') { out.pop(); continue }
    out.push(part)
  }
  return '/' + out.join('/')
}

/**
 * Whether a token from an agent's terminal is a reference to a file of ONE
 * checkout — and if so, which file and which line.
 *
 * The narrow question: does this token name a file THIS listing has. The wider
 * one — which of several checkouts, a directory, a suffix match, the desktop —
 * is `terminalTarget`'s, and it is deliberately not folded in here: this
 * function is the proof step, and a proof that also guesses is not one.
 *
 * ## The text is data, not an instruction
 *
 * Everything in a terminal was written by whatever the agent ran, so the two
 * rules here are refusals: an absolute path counts only inside this checkout,
 * and a relative one only when the checkout actually has that file.
 */
export function fileReference(
  token: string,
  root: string,
  known: ReadonlySet<string>,
): FileRef | null {
  const normalisedRoot = root.replace(/\/+$/, '')
  for (const candidate of unwrapCandidates(token)) {
    for (const ref of pathAndLine(candidate)) {
      let rel = ref.path
      if (!rel) continue
      if (rel.startsWith('/')) {
        if (insideCheckout(rel, [normalisedRoot]) === null) continue
        rel = rel === normalisedRoot ? '' : rel.slice(normalisedRoot.length + 1)
      }
      rel = rel.replace(/^\.\//, '')
      if (!rel || !known.has(rel)) continue
      return ref.line === undefined ? { path: rel } : { path: rel, line: ref.line }
    }
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
 * read nothing. Which of the two answers a given token is `terminalTarget`.
 *
 * ## The rules, and why each one is a refusal
 *
 *  - **no `://`.** A URL is the other link provider's business, and handing one
 *    to a desktop opener is how a `file:` or a `javascript:` scheme gets a
 *    second chance at being followed.
 *  - **a trailing `:<line>` is dropped.** A desktop handler takes no line
 *    number, and `/tmp/run.log:42` should still open `/tmp/run.log`.
 *  - **a relative token needs a BASE to resolve against.** Without one it stays
 *    text rather than being resolved against a working directory the reader
 *    cannot see.
 *  - **and a relative token must LOOK like a path**, which is the load-bearing
 *    one. `fileReference` keeps prose out by checking the known set; this route
 *    has no such set, so the shape is the only filter left.
 *
 * What it does NOT check is whether the path exists, and that is a decision.
 * Asking the server would answer "is there a file at X" for any path on the
 * machine, one request at a time — the oracle the file endpoints refuse to be.
 */
export function desktopReference(token: string, base?: string): string | null {
  for (const candidate of unwrapCandidates(token)) {
    if (candidate.includes('://') || candidate.startsWith('//')) continue
    const written = (pathAndLine(candidate)[0]?.path ?? candidate).replace(/^\.\//, '')
    if (!written) continue
    const path = withoutTrailingSlash(written)
    if (path.length < 2) continue
    if (path.startsWith('/')) return path
    const normalisedBase = base?.replace(/\/+$/, '') ?? ''
    if (!normalisedBase) continue
    if (!looksLikePath(written)) continue
    return normalisedBase + '/' + path
  }
  return null
}

/** What the recogniser is told about where this terminal's agent is standing. */
export interface TerminalWhere {
  /** The project's own checkout — the fallback base. */
  root?: string
  /** Where the agent is STANDING. The base for every relative token. */
  cwd?: string
  /** The base checkout's listing, as a plain set. Superseded by `listing`. */
  known?: ReadonlySet<string>
  /** The base checkout's listing, indexed — adds directories and suffixes. */
  listing?: ListingIndex
  /**
   * Every checkout the file endpoints will serve: each registered project's
   * root, and each non-prunable worktree of one.
   *
   * The browser is told which checkouts EXIST; it never asks the server about a
   * path. Shipping the roots rather than the listings is a decision about SIZE
   * — one consumer checkout lists 30 121 files — and the consequence is stated
   * rather than discovered: an absolute path into a registered checkout links
   * even when its listing was never fetched, because the prefix answers. The
   * panel then opens it and the ENDPOINT decides. That is the correct division:
   * the endpoint is the guard, the browser is a router.
   */
  checkouts?: readonly string[]
  /** The framework account's home, for `~/`. The browser never guesses it. */
  home?: string
}

/**
 * THE ONE PLACE that decides where a terminal token goes.
 *
 * ## The three tiers, in order
 *
 * ```
 * inside a checkout the endpoints serve            → internal, underlined
 * ≥2 segments AND an extension on the last segment → desktop, underlined
 * anything else absolute and path-shaped           → LOW confidence
 * neither                                          → text
 * ```
 *
 * ## The worktree, which is what the `cwd` base was written for
 *
 * Reported 2026-08-26 from a live screen: an agent working in a worktree on a
 * change branch printed a relative path, and the dashboard resolved it against
 * the PROJECT ROOT — a different checkout on a different branch. Two ways that
 * goes wrong, and the second is worse than the error the reader saw: the path
 * is missing there, or it EXISTS there and the reader is silently shown the main
 * branch's copy. A wrong file that opens is worse than a right one that refuses.
 *
 * ## Proof beats shape
 *
 * Where the listing HAS the path, the shape test is not consulted. The shape
 * test is a proxy for "is this a path"; the listing answers that question
 * directly, and consulting a proxy over an answer is how a Next.js dynamic
 * route file (`src/app/items/[id]/page.tsx`) becomes unopenable in its own
 * project for carrying a bracket.
 */
export function terminalTarget(token: string, where: TerminalWhere): TerminalTarget {
  const base = (where.cwd || where.root || '').replace(/\/+$/, '')
  const files = where.listing?.files ?? where.known
  /*
    WHICH checkouts count as servable, and why the base is not simply added.

    A supplied list is the SERVER's answer and is trusted exclusively: it is
    derived from the same verdict the endpoints apply, so adding to it in the
    browser would be a second opinion about what the framework may read.

    The base is the fallback for a caller that supplied no list but did supply a
    listing — which is the older payload, and the tests. It is NOT added
    alongside a supplied list, and that is a real difference rather than tidying:
    an agent's cwd is not always a checkout (a process discovered standing in a
    build directory), and treating it as one resolves relative tokens against a
    place the endpoints would refuse, instead of against the project root that
    contains it.

    A caller that supplied neither gets exactly the old behaviour: a base to
    resolve relative tokens against, and the desktop as the only destination.
  */
  const checkouts = [...(where.checkouts ?? [])]
  if (checkouts.length === 0 && base && (files !== undefined || where.listing !== undefined)) {
    checkouts.push(base)
  }

  /*
    MOST-STRIPPED FIRST, and inside each candidate the listing is consulted
    before the shape rule. Two decisions, and each has a measurement behind it.

    The ORDER: the punctuation an agent's prose leaves on a path is far commoner
    than a filename that ends in one. Measured with the order the other way
    round — `<checkout>/.venv/bin/python:` and `<checkout>/src/lib/__tests__,`
    both kept their trailing character and named nothing, because INSIDE a
    checkout every candidate places and the first one therefore wins.

    Its bounded cost, stated rather than left to be discovered: a file whose real
    name ends in a full stop loses to the stripped reading of it. Only the full
    stop is at risk — every other character this strips (`)`, `]`, `,`, `` ` ``,
    `:`) is outside the path-character class, so the over-stripped candidate is
    refused on its shape and the next one is reached.

    PROOF BEFORE SHAPE, per candidate: where the listing HAS the path, the shape
    test is not consulted. The shape test is a proxy for "is this a path", and
    consulting a proxy over an answer is how a Next.js dynamic-route file
    becomes unopenable in its own project for carrying a bracket.

    A token carrying a star is offered ONLY to the listing — see `carriesGlob`.
  */
  const candidates = unwrapCandidates(token)
    .filter(c => !c.includes('://') && !c.startsWith('//'))
    .reverse()
  const provenOnly = carriesGlob(token)
  for (const candidate of candidates) {
    for (const ref of pathAndLine(candidate)) {
      const target = classify(ref, base, checkouts, files, where, provenOnly)
      if (target) return target
    }
  }
  return null
}

function classify(
  ref: FileRef,
  base: string,
  checkouts: readonly string[],
  files: ReadonlySet<string> | undefined,
  where: TerminalWhere,
  /** Proof only: a listing hit, a directory of one, or a unique suffix. */
  provenOnly: boolean,
): TerminalTarget {
  const written = ref.path
  if (!written) return null

  const hintDir = written.endsWith('/')
  let abs: string

  if (written.startsWith('~/')) {
    // The home is the framework account's, supplied by the server. A browser
    // that guessed it would link to a file belonging to somebody else.
    if (!where.home) return null
    abs = where.home.replace(/\/+$/, '') + written.slice(1)
  } else if (written.startsWith('/')) {
    abs = written
  } else if (written.startsWith('~')) {
    return null
  } else {
    const rel = withoutTrailingSlash(written.replace(/^\.\//, ''))
    if (!rel || rel === '.' || rel === '..') return null
    if (!base) return null

    // Proof first: the listing HAS this path, so nothing else needs to vouch.
    if (files?.has(rel)) return { kind: 'file', ref: { ...ref, path: rel }, root: base, confidence: 'high' }
    if (where.listing?.dirs.has(rel)) {
      return { kind: 'directory', path: rel, root: base, confidence: 'high' }
    }
    // A token no listing has as a whole path may still be the TAIL of exactly
    // one. Where several match, the reader chooses — see `suffixMatches`.
    const matches = suffixMatches(where.listing, rel)
    if (matches.length === 1) {
      return { kind: 'file', ref: { ...ref, path: matches[0] }, root: base, confidence: 'high' }
    }
    if (matches.length > 1) {
      return {
        kind: 'choice',
        matches: matches.map(path => (ref.line === undefined ? { path } : { path, line: ref.line })),
        root: base,
        confidence: 'high',
      }
    }
    if (provenOnly) return null
    // The shape test sees the token AS WRITTEN, `./` included, because that
    // prefix is the writer saying "this is a path". Measured both ways over the
    // corpus: dropping it turned 74 references to real files and directories
    // into plain text to remove ~33 extensionless import specifiers. The
    // residue is stated rather than hidden — `./helpers/auth` in an import
    // statement is a link that answers "no such file".
    if (!looksLikePath(written)) return null
    abs = base + '/' + rel
  }

  const path = withoutTrailingSlash(normalise(abs))
  if (path.length < 2) return null

  const checkout = insideCheckout(path, checkouts)
  if (checkout !== null) {
    const rel = path === checkout ? '' : path.slice(checkout.length + 1)
    if (!rel) return { kind: 'directory', path: '', root: checkout, confidence: 'high' }
    if (files?.has(rel)) return { kind: 'file', ref: { ...ref, path: rel }, root: checkout, confidence: 'high' }
    if (where.listing?.dirs.has(rel)) {
      return { kind: 'directory', path: rel, root: checkout, confidence: 'high' }
    }
    if (provenOnly) return null
    // Unproven, but inside a checkout the endpoints serve. No shape test: the
    // prefix IS the evidence, and a prose filter on top of it costs real files
    // — a Next.js dynamic route, a build directory the listing excludes. What
    // the endpoint will not serve, the endpoint refuses.
    if (hintDir) return { kind: 'directory', path: rel, root: checkout, confidence: 'high' }
    return { kind: 'file', ref: { ...ref, path: rel }, root: checkout, confidence: 'high' }
  }

  if (provenOnly) return null

  // Outside every checkout the endpoints serve. Nothing here is ever read.
  if (!PATH_CHARS.test(path)) return null
  const segments = path.split('/').filter(Boolean)
  const last = segments[segments.length - 1] ?? ''
  const placed = segments.length >= 2 && /\.[A-Za-z0-9]+$/.test(last)
  return { kind: 'desktop', path, confidence: placed ? 'high' : 'low' }
}

/**
 * Every listing path that ends with `token` on a path BOUNDARY.
 *
 * A uniqueness test and never a best match: 50 tokens over the measured corpus
 * end exactly one listing path and 13 end several. Only the unique ones resolve
 * to a file. Never "the shortest", never "the first" — a wrong file that opens
 * looks exactly like a right one, and nothing on the screen says otherwise.
 *
 * The boundary is what keeps `actions/dashboard.ts` from matching
 * `.../my-actions/dashboard.ts`.
 */
function suffixMatches(listing: ListingIndex | undefined, token: string): string[] {
  if (!listing) return []
  const tail = token.split('/').pop() ?? ''
  const bucket = listing.tails.get(tail)
  if (!bucket) return []
  const needle = '/' + token
  return bucket.filter(path => path.endsWith(needle))
}

/** One recognised reference in a terminal row, with where it sits. */
export interface Reference {
  /** 0-based column in the row where the token starts. */
  index: number
  token: string
  target: NonNullable<TerminalTarget>
}

/**
 * Every reference in ONE terminal row, within the recogniser's limits.
 *
 * Here rather than in the component so the limits are measurable without a
 * browser — a bound nothing can test is a bound nobody will notice going wrong.
 * A row past the length limit is not scanned AT ALL rather than scanned partly:
 * a partial scan of a long row produces links whose columns are right and whose
 * coverage is arbitrary, which is worse than none.
 */
export function terminalReferences(row: string, where: TerminalWhere): Reference[] {
  const found: Reference[] = []
  if (!row || row.length > RECOGNISER_LIMITS.row) return found
  const re = /\S+/g
  let m: RegExpExecArray | null
  while ((m = re.exec(row)) !== null) {
    if (m[0].length > RECOGNISER_LIMITS.token) continue
    const target = terminalTarget(m[0], where)
    if (!target) continue
    found.push({ index: m.index, token: m[0], target })
    if (found.length >= RECOGNISER_LIMITS.perRow) break
  }
  return found
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
