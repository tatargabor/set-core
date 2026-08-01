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
