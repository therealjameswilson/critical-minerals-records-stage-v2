# Notes for Claude

Working preferences and environment quirks for this repo. Auto-loaded at
session start.

## Working style

**Ask before implementing non-trivial changes.** Lay out the plan in plain
text, name any refactors or fork-in-the-road decisions, and wait for
sign-off. Examples of "ask first":

- Multi-file edits, especially across the setup tool (`app.py`) and the
  publishing tool (`records-stage.html`)
- Lifting helpers to new modules or extracting new files
- Choice of library, branch strategy, commit-grouping
- Anything where reasonable people would pick differently

For one obvious next step — a clear bug fix that's just been described, or
a small edit to fulfill an explicit request — proceed and narrate.

When asking, plain-text numbered options work; an interactive question
tool may be flaky.

## Environment quirks

**Git write operations from the Cowork sandbox leave orphan files** in
`.git/` (a stuck `index.lock` plus tens of `tmp_obj_*` files in
`.git/objects/`) that the sandbox can't subsequently delete. This is a
permission mismatch between the host and the sandboxed shell.

Implications:

- `git stash`, `git checkout`, `git commit`, `git branch`, `git push` —
  don't run these from the sandbox. Hand them off to the user's Mac
  terminal as a paste-ready shell block.
- `git status`, `git log`, `git diff` — fine, work despite cleanup
  warnings.
- If the sandbox somehow gets locked anyway, the user's cleanup is:
  ```
  rm -f .git/index.lock
  find .git/objects -name "tmp_obj_*" -delete
  ```

## Repo orientation

Flat layout — modules sit at the repo root, not inside a package.
`tests/conftest.py` adds the root to `sys.path` so the tests can import
`app`, `html_embed`, `build_cache`, etc. directly.

Two pieces of related work that go through `records-stage.html`:

- The publishing tool itself (rendered standalone in a browser)
- The setup tool (`app.py`, a Streamlit wrapper) that rewrites two
  marker-delimited JS regions inside it: `/* CLEARANCE_DEFAULTS */` and
  `/* DRAFTED_BY */`. Those markers are load-bearing.

The publishing tool's image-search modal pulls from three sources, each a
tab with its own filters: **NARA Catalog** (via the `nara_proxy_worker.js`
Cloudflare Worker) plus **Wikimedia Commons** and **Library of Congress**
(both browser-direct -- loc.gov blocks the Worker's datacenter IP but serves
a real browser). The LoC tab filters by material type using loc.gov's
`original-format` facet. Keep `nara_proxy_worker.js` ASCII-only -- it is
pasted into the Cloudflare dashboard, where stray non-ASCII comment
characters can corrupt and break the deploy.

The events cache (`events_cache.json` + `events_cache.js`) is gitignored;
regenerate it with `build_cache.py` and re-splice into
`records-stage.html` via `html_embed.sync_html_embed`.
