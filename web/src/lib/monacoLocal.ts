/**
 * Monaco, loaded from THIS build and never from a CDN.
 *
 * `@monaco-editor/react` defaults to fetching Monaco from jsdelivr at runtime.
 * That default is the dangerous kind: it works on a developer's machine with a
 * network and fails on the machine this dashboard actually runs on — a local
 * server, often with no route out — and it fails at the moment somebody opens a
 * file, not at build time. The failure direction is the reassuring one: every
 * test passes, the bundle builds, and the feature is broken only where it is
 * used.
 *
 * So the loader is pointed at the bundled `monaco-editor` package, and the
 * workers are Vite-bundled assets of this build too.
 *
 * ## Why this module is imported dynamically
 *
 * Importing it pulls Monaco itself into the graph — the largest dependency in
 * `web/` by a wide margin. `FleetFileView` imports it inside an effect, exactly
 * as `FleetTerminal` imports xterm, so a reader who never opens a file never
 * downloads an editor.
 */
import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'

/*
  The worker paths go through monaco-editor's OWN exports map, which rewrites
  `monaco-editor/<x>` to `esm/vs/<x>.js` (measured in its package.json at 0.56).
  Writing the `esm/vs/...` path directly — the shape most guides still show —
  fails to resolve at build time, which is at least a loud failure rather than a
  quiet CDN fallback.
*/
import editorWorker from 'monaco-editor/editor/editor.worker?worker'
import jsonWorker from 'monaco-editor/language/json/json.worker?worker'
import cssWorker from 'monaco-editor/language/css/css.worker?worker'
import htmlWorker from 'monaco-editor/language/html/html.worker?worker'
import tsWorker from 'monaco-editor/language/typescript/ts.worker?worker'

let configured = false

/**
 * Make Monaco available, once.
 *
 * Idempotent because several panels may mount and unmount over a session and
 * `loader.config` may only be called before the first `loader.init()`. A second
 * call after initialisation throws, which would take the panel down for a reason
 * that has nothing to do with the file being opened.
 */
export function useLocalMonaco(): typeof monaco {
  if (!configured) {
    configured = true
    ;(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
      getWorker(_: unknown, label: string) {
        if (label === 'json') return new jsonWorker()
        if (label === 'css' || label === 'scss' || label === 'less') return new cssWorker()
        if (label === 'html' || label === 'handlebars' || label === 'razor') return new htmlWorker()
        if (label === 'typescript' || label === 'javascript') return new tsWorker()
        return new editorWorker()
      },
    }
    loader.config({ monaco })
  }
  return monaco
}
