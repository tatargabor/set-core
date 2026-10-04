"""feed-watch — watch a web feed for items worth a human's reply.

The module is domain-free. A project declares everything that carries domain in
`.set/feed-watch.yaml`: the sources, the rubric, the threshold, the labels in its own
language, the draft template and the copy gate. set-core ships none of those.

Two rules hold for everything in this package:

- **Nothing here touches the network.** Collection is agent work through the user's own
  browser (the deployed skill drives it); this package does the deterministic parts.
- **Nothing derived from an item is logged or persisted outside the project's tree.**
  Logs carry counts and file names, never item text, authors or contact details.
"""
