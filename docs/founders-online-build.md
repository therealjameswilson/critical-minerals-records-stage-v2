# Building the Founders Online tool

Founders Online (National Archives) publishes metadata for ~184,138 documents —
the correspondence and papers of **John Adams, Benjamin Franklin, Alexander
Hamilton, John Jay, Thomas Jefferson, James Madison, and George Washington**,
spanning **1706–1923** (seven editions). This repo turns that corpus into the
**`founders-online-stage.html`** publishing tool, built by
**`build_founders_stage.py`**.

It is the standard Records Stage UI — same shell as `records-stage.html` /
`federal-register-stage.html`: the preset campaign builder, clearance editor,
Word export, and the shared NARA + Wikimedia Commons + Library of Congress
image-search modal — with the Founders corpus spliced in. It embeds its own copy
of the data, so it needs no server or network at run time.

---

## 1. The source data

Each record carries only:

```
title, permalink, project (edition), authors[], recipients[], date-from, date-to
```

- **99.7%** (183,500) have a full `YYYY-MM-DD` date; the builder drops the 638
  blank/partial-date records.
- All **366 calendar days** are covered (busiest: Jan 1, partly an artifact of
  year-only dates defaulting upstream to January 1).
- Licensing: the annotated documents are the work of the **University of
  Virginia Press**, released under **CC-BY-NC**. The tool stores metadata only
  and links back to founders.archives.gov for every document.

### Downloading the metadata (manual, one-time)

The bulk file is behind an **AWS WAF JavaScript challenge**, so a scripted
`curl`/`requests` fetch fails (you get an `HTTP 202` challenge page, not the
JSON). Download it in a real browser:

```
https://founders.archives.gov/Metadata/founders-online-metadata.json
```

and save it at the repo root as `founders-online-metadata.json`. It is
gitignored — large and re-downloadable; the generated HTML embeds its own
compact copy, so the raw file is only needed at build time.

---

## 2. Building it

```bash
python build_founders_stage.py
```

This is the convention-matching build, parallel to `build_fr_cache.py`: it maps
the metadata onto the toolkit's **event contract** and splices it into a fresh
copy of the cleared, vendored `records-stage.html` shell via
`html_embed.sync_html_embed`. **It does not edit the shared shell** — the result
is the canonical Records Stage UI with Founders data.

Mapping (`event_contract.py`):

| Field | Source |
|---|---|
| `source` | the **edition** (`Washington Papers`, `Adams Papers`, …) — so the shell's auto-discovered source-filter chips become **per-founder filters** (7 chips). |
| `year` / `month` / `day` | from `date-from`; month/day zero-padded so the bucket key matches the shell's `String(month).padStart(2,"0")` lookup. |
| `title` / `url` | document title / permalink. |

No score (the shell only badges / min-score-filters FRUS), and no subjects
(Founders metadata carries none, so the topic filter stays inert — same as the
Federal Register presidential side). The compact event is therefore just
`{y, t, u, s}`, which keeps the embedded cache to ~24 MB; the finished
`founders-online-stage.html` is ~30 MB.

What you get for free from the shell: the multi-tweet **preset** campaign
builder, real-time character counting, the **clearance editor**, **Word
export**, and the **image-search modal** (NARA Catalog via the proxy worker,
plus Wikimedia Commons and Library of Congress browser-direct).

Build intermediates `founders_events_cache.json` / `.js` are gitignored
(regenerable; the HTML embeds the data).

---

## 3. Data caveats (documented, not silently corrected)

- **Search is title-only** — the bulk metadata has no subject tags or body text.
- **~5.5% cross-edition duplication** — Founders Online publishes a letter in
  *both* correspondents' editions (e.g. a Jefferson→Madison letter appears in
  the Jefferson Papers and the Madison Papers as two records with different
  permalinks). Left intact because the editions' annotations differ; it inflates
  counts.
- **Jan 1 spike** — year-only-known dates default upstream to January 1.
