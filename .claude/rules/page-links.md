# Page Links — everything a page names opens with one click

Sibling of [file-references](file-references.md): that rule makes a path in **chat** openable;
this one does the same for a **page** you publish or write — a claude.ai artifact, a local HTML
report, a preview or approval page.

Stated by the owner on 2026-11-26, about an approval page whose attachments were listed as plain
file names: the links must open in a new tab, nobody should have to copy them out, and the same
goes for files.

## The rule

- **A web address** → a real link: `<a href="https://…" target="_blank" rel="noopener">`.
  Never a URL as bare text the reader has to copy.
- **A file the page talks about** — an attachment, a PDF, an image, a generated output — is
  clickable too. How depends on where the page lives (below).
- **`mailto:` / `tel:`** are unreliable inside an artifact. Link them, but keep the address
  visible as text as well, and never claim something was sent because the reader tapped one.

## Files inside a claude.ai artifact — measured, not assumed

Measured 2026-11-26 on a live artifact:

- A plain link to a file **published beside the page** (`<a href="doc.pdf" target="_blank">`)
  does **not** open. The host shows *"This file can't be opened here"*.
- The file's own frame URL (`…frame.claudeusercontent.com/_f/<version>/doc.pdf`) opened in a
  new tab **redirects back to the artifact page**. There is no direct file URL to link to.
- What works: the page `fetch()`es the file by **relative URL** and shows it in an **in-page
  viewer**. For a PDF: pdf.js from cdnjs (pinned version, worker from the same path), every
  page rendered to a canvas inside a fixed overlay, closable with a button and Esc. Clicking
  the file name, and the preview image of it if there is one, opens the viewer.

So in an artifact, "opens with one click" means the in-page viewer, not a new tab — the frame
does not allow the latter. Re-measure before relying on this if the artifact host changes.

## Files in a local HTML page

Link the file with `file://` + its **absolute** path. This is the display side of
"store relative, display absolute" from file-references: the page is for a human to open, so
the path must resolve wherever the page is opened from.

## Why this is a rule

A name the reader has to copy is the same failure as a relative path: nothing errors, nothing
warns, and the cost lands on the reader every single time they open the page.
