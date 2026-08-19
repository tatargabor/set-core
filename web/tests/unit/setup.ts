/**
 * What jsdom does not implement, supplied here rather than worked around in the product.
 *
 * `ResizeObserver` is the one that matters: the table watches its own box so it can say how many
 * columns are off to the right, and that count has to be re-taken when the box changes width.
 * jsdom has no layout engine and therefore no observer, so 78 tests failed at once on a missing
 * global — an environment gap, not 78 defects.
 *
 * Deliberately NOT solved with a `typeof ResizeObserver !== 'undefined'` guard in the component.
 * A guard makes the product quietly do less in an environment nobody notices, and it makes every
 * test run against a code path the browser never takes. The stub belongs where the gap is.
 *
 * It observes nothing on purpose. jsdom reports every box as zero-sized, so a callback firing
 * here could only deliver a fictional measurement — and a fictional zero would read as "no
 * hidden columns", which is exactly the false-absence this surface refuses elsewhere. The
 * geometry is asserted in the browser, by the Playwright pass.
 */
class NoopResizeObserver implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = NoopResizeObserver as unknown as typeof ResizeObserver
}

/**
 * `localStorage`, for the same reason and with the same rule as above.
 *
 * Measured 2026-08-19 in this environment: the global exists and is a PLAIN
 * OBJECT — `typeof localStorage === 'object'`, prototype `Object.prototype`,
 * no `getItem`, no `setItem`. So a `typeof localStorage === 'undefined'` guard
 * would not have caught it, and `localStorage.setItem(...)` raises
 * `TypeError: localStorage.setItem is not a function`.
 *
 * That failure direction is the one worth naming: the product code wraps its
 * storage access in `try/catch` (a browser can genuinely refuse storage), so
 * the missing methods were swallowed and the screen simply behaved as though
 * nothing was ever remembered. Every assertion about a remembered choice would
 * have failed against a component that is correct in a browser — and one about
 * "nothing is remembered" would have PASSED for the wrong reason.
 *
 * The stub is a real in-memory Storage rather than a mock that records calls:
 * a test asserting "setItem was called" would pass on a build that writes the
 * wrong key, which is exactly the mechanism-not-result defect.
 */
function installStorage(name: 'localStorage' | 'sessionStorage') {
  const existing = (globalThis as Record<string, unknown>)[name]
  if (existing && typeof (existing as Storage).setItem === 'function') return
  const map = new Map<string, string>()
  const storage: Storage = {
    get length() { return map.size },
    key: (i: number) => Array.from(map.keys())[i] ?? null,
    getItem: (k: string) => (map.has(k) ? map.get(k)! : null),
    setItem: (k: string, v: string) => { map.set(String(k), String(v)) },
    removeItem: (k: string) => { map.delete(String(k)) },
    clear: () => { map.clear() },
  }
  Object.defineProperty(globalThis, name, { value: storage, configurable: true, writable: true })
}

installStorage('localStorage')
installStorage('sessionStorage')

/**
 * `Element.prototype.scrollIntoView`, absent from jsdom for the same reason as
 * `ResizeObserver`: there is no layout, so there is nowhere to scroll to.
 *
 * A no-op, and the limit is stated rather than papered over — with this stub a
 * test can assert that the jump REVEALED its target (opened the collapsed group
 * it was hiding in), and it can assert nothing whatsoever about the element
 * actually coming into view. That half is a geometry claim and only the browser
 * pass can make it.
 *
 * Stubbed here rather than guarded at the call site: a `?.` in the product would
 * make the real screen silently skip the scroll the day some other environment
 * lacked it, and nobody would be told.
 */
if (typeof Element !== 'undefined' && typeof Element.prototype.scrollIntoView !== 'function') {
  Element.prototype.scrollIntoView = function scrollIntoView() { /* no layout in jsdom */ }
}
