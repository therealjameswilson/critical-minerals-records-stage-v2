# Building the Federal Register Records Stage

How to build the combined **Federal Register — Records Stage**
(`federal-register-stage.html`) from a clean checkout, using the Records Studio
pipeline. The finished tool is an "On This Day" campaign builder over two
Federal Register sources — **Presidential Documents** and **State Department**
filings — with source-filter chips, a doc-type filter, and a themed topic
filter.

This guide is reproducible end-to-end: with no data fetched at all, the build
still runs and produces a working tool from the checked-in seed samples.

---

## 1. How this maps to the Records Studio pipeline

The toolkit's pipeline is always the same four seams; an adopter supplies the
first three and the kit does the rest:

1. **Parser** — walk raw source data, emit normalized event dicts
   (`docs/data-contract.md`).
2. **Scorer** — return an integer score per event (the editorial threshold).
3. **Taxonomy** *(optional)* — a controlled vocabulary for the subject filter.
4. **Build** — validate → score → bucket by `MM-DD` → write `*_events_cache.json`
   (full) + `*_events_cache.js` (compact) → splice into the HTML
   (`html_embed.sync_html_embed`).

The Federal Register edition fills those seams like this:

| Seam | Federal Register edition |
|---|---|
| Parser | `data/federal-register/parser.py` (presidential docs) + `data/state-department/parser.py` (State filings). Each has a `fetch_*.py` that pulls raw JSON from the Federal Register API first. |
| Scorer | `score_event()` / `threshold()` live **inside each adapter** (light doc-type ranking; threshold 0, so nothing is dropped). |
| Taxonomy | Synthesized at build time from the Federal Register's own subjects, grouped into broad themes by `fr_themes.py`. |
| Build | `build_fr_cache.py` — a dedicated **combined** builder that runs both adapters into one cache and splices `federal-register-stage.html`. |

### Why a dedicated builder instead of `build_cache.py`

The generic `build_cache.py` imports a single `parser.py` / `scorer.py` at module
load and writes the repo's default `events_cache.*`. The Federal Register edition
differs in three ways: it folds in **two** sources, it keeps its **own** cache
(`fr_events_cache.*`) so the repo's default tool is untouched, and it must not
depend on the repo's default `parser.py` wiring. So `build_fr_cache.py` reuses
only the toolkit's leaf modules — `cache_format` (field map), `event_contract`
(validation), `html_embed` (safe embedding + splice) — and reimplements the
short bucket/compact loop. It produces byte-compatible output; it just isn't
routed through `build_cache.build`.

> The Streamlit **Records Studio** wizard (`app.py`) is built around a single
> parser and the default cache, so it's the right tool for a one-source
> adoption. For this two-source edition, use the command-line builder below.

---

## 2. Prerequisites

- Python 3.10+
- `pip install -r requirements.txt` (the build itself needs only the standard
  library; the fetchers use `urllib`, no third-party HTTP client)
- **No API key.** The Federal Register API is public, key-free, and
  CORS-enabled, so neither the fetchers nor the tool's live features need a
  proxy.
- Node is optional (only used for the verification snippet in §7).

---

## 3. Files involved

```
data/federal-register/
  fetch_fr.py                       # pulls presidential documents from the API
  parser.py                         # parse_corpus() + score_event() + threshold()
  presidential_documents.sample.json# seed (real records, used if no full fetch)
  presidential_documents.json       # full fetch output (gitignored)
  README.md
data/state-department/
  fetch_state.py                    # pulls State Dept documents (agency filter)
  parser.py
  state_documents.sample.json       # seed
  state_documents.json              # full fetch output (gitignored)
  README.md
fr_themes.py                        # theme_for(): buckets FR subjects into themes
build_fr_cache.py                   # COMBINED builder (both sources) -> FR cache + HTML splice
build_state_cache.py                # standalone State-only builder (optional)
cache_format.py                     # compact field map (+ pr/eo/ci keys for FR)
fr_events_cache.json / .js          # build output
federal-register-stage.html         # the tool (cache spliced in)
```

---

## 4. Build it (the short version)

From the repo root:

```bash
# 1. Fetch both corpora (a few minutes; no key needed)
python data/federal-register/fetch_fr.py        # ~8,500 presidential docs, 1994-present
python data/state-department/fetch_state.py      # ~10-12k State Dept docs, 1994-present

# 2. Build the combined cache and splice it into the tool
python build_fr_cache.py

# 3. Open it
open federal-register-stage.html
```

That's the whole pipeline. If you skip step 1, step 2 still works — each adapter
falls back to its checked-in seed sample, so you get a small but fully
functional tool immediately.

Expected build output (counts depend on fetch date):

```
events_by_source: {'Presidential Documents': 8507, 'State Department': 11183}
total_events: 19690
days_with_events: 365
taxonomy_subjects: 646
html_synced: True
```

---

## 5. What each step does, in detail

### 5.1 Fetch — `fetch_fr.py` and `fetch_state.py`

Both are pure-stdlib scripts that page the Federal Register documents endpoint
one publication year at a time (the API caps offset pagination at the first
2,000 results per query; a single year is well under that) and write raw JSON
next to themselves.

- `fetch_fr.py` filters by **document type**: `conditions[type][]=PRESDOCU`
  (executive orders, proclamations, presidential memoranda, determinations,
  notices). Output: `data/federal-register/presidential_documents.json`.
- `fetch_state.py` filters by **agency**: `conditions[agencies][]=state-department`
  (agency id 476). Output: `data/state-department/state_documents.json`.

Shared options:

```bash
python data/federal-register/fetch_fr.py --since 2009            # Obama-onward only
python data/federal-register/fetch_fr.py --until 2025
python data/federal-register/fetch_fr.py --out /tmp/pd.json
```

The requested fields are kept minimal and explicit so the payload stays small;
notably `fetch_state.py` also requests `topics` (CFR indexing terms) and
`toc_subject` (the FR table-of-contents grouping), which feed the topic filter.

### 5.2 Parse + score — the adapters

Each `parser.py` exposes `parse_corpus(source_root)`, `score_event(event)`, and
`threshold()`.

Presidential adapter (`data/federal-register/parser.py`):

- **Date key** = `signing_date`, falling back to `publication_date`.
- `source = "Presidential Documents"`.
- `extra.doc_type` = the document subtype (Executive Order, Proclamation, …).
- `extra.president`, `extra.eo_number` (e.g. "E.O. 14406"), `extra.citation`
  (e.g. "91 FR 30479").
- Score by subtype (EO 40 → Notice 15), threshold 0.

State adapter (`data/state-department/parser.py`):

- **Date key** = `publication_date` (State filings carry no signing date).
- `source = "State Department"`.
- `extra.doc_type` = the FR document type (Notice, Rule, Proposed Rule).
- `subjects` = `topics` if present, else the cleaned `toc_subject`. These drive
  the topic filter.
- Score by type (Rule 30 → Notice 10, +5 if `significant`), threshold 0.

> **Data contract reminder:** month/day must stay zero-padded ("05", "19") so the
> `MM-DD` bucket key matches the tool's date-browse lookup. The API already
> returns padded dates — keep them.

### 5.3 Themes — `fr_themes.py`

The Federal Register's subject vocabulary is flat (hundreds of CFR terms with no
hierarchy). `theme_for(name)` runs ordered keyword rules to bucket each subject
into one of ~16 broad themes (Sanctions & Export Control, Immigration/Passports
& Consular, Treaties, Cultural/Educational & Exchange, etc.). The builder uses
the theme as the taxonomy's top tier (Category), leaving the subcategory level
trivial — which the tool auto-collapses into an "All of <theme>" shortcut,
giving a clean **Theme → Subject** filter.

To re-bucket subjects, edit the keyword lists in `fr_themes.py` and rebuild. The
catch-all "Other" bucket is the lever: shrink it by adding keywords.

### 5.4 Build — `build_fr_cache.py`

The combined builder:

1. Loads both adapters (see the `SOURCES` list at the top of the file).
2. For each source: `parse_corpus()` → validate against `event_contract` →
   `score_event()` → keep if `>= threshold()`.
3. Synthesizes the themed taxonomy from all subjects via `fr_themes.theme_for`,
   then sets each event's `subject_indices`.
4. Buckets by `MM-DD`, sorts each day by score.
5. Writes `fr_events_cache.json` (full) and `fr_events_cache.js` (compact, with
   `SUBJECT_TAXONOMY` + `EVENTS_CACHE` globals).
6. Splices the compact cache into `federal-register-stage.html` via
   `html_embed.sync_html_embed`.

Options:

```bash
python build_fr_cache.py --no-html-sync       # write the cache but don't touch the HTML
python build_fr_cache.py --html path/to.html  # splice a different HTML file
```

### 5.5 The compact format — `cache_format.py`

The compact JS keys are defined in `cache_format.COMPACT_FIELD_MAP` (core
fields) and `COMPACT_EXTRA_FIELDS` (per-source extras). The Federal Register
edition added three extras, which only appear when present so other sources are
unaffected:

| `extra` key | compact key | shown as |
|---|---|---|
| `president` | `pr` | a tag on presidential cards |
| `eo_number` | `eo` | instrument-number tag (e.g. "E.O. 14406") |
| `citation` | `ci` | used in AI-draft context |

### 5.6 The HTML shell — `federal-register-stage.html`

A copy of the vendored Records Stage with edition-specific wiring:

- Two `SOURCE_META` entries ("Presidential Documents", "State Department") with
  badge colors, so the **source-filter chips** render and toggle.
- A **data-driven doc-type filter**: the dropdown is populated at load from the
  distinct `dt` values actually in the cache, so it always matches the data
  (no manual option list).
- The card renderer surfaces `pr`/`eo` tags for presidential events; State
  events show their doc type and feed the topic filter.
- FRUS-specific machinery (score sort, classification tags, War/Era preset) was
  removed — this is a Federal Register tool.

Because the data is **embedded** (spliced by `build_fr_cache.py`), the finished
HTML is self-contained and opens directly in a browser — no server.

---

## 6. Refreshing later

The Federal Register publishes continuously. To pull new documents and rebuild:

```bash
python data/federal-register/fetch_fr.py
python data/state-department/fetch_state.py
python build_fr_cache.py
```

`build_fr_cache.py` always rebuilds the whole FR cache (it's small — tens of
thousands of events, a few MB). There's no need for the incremental
`merge_sources.py` path here; that's for corpora where one source is expensive
to re-parse.

---

## 7. Verifying a build

Quick structural check with Node (optional):

```bash
node -e "
const fs=require('fs');
eval(fs.readFileSync('fr_events_cache.js','utf8').replace(/const /g,'var '));
const all=[];for(const k in EVENTS_CACHE)for(const e of EVENTS_CACHE[k])all.push(e);
const bySrc={};all.forEach(e=>bySrc[e.s]=(bySrc[e.s]||0)+1);
console.log('events by source:',bySrc);
console.log('doc types:',[...new Set(all.map(e=>e.dt))]);
console.log('themes:',[...new Set(SUBJECT_TAXONOMY.map(t=>t.c))]);
"
```

Then open `federal-register-stage.html` and confirm: both source chips appear,
the doc-type dropdown lists EO/Proclamation/Notice/Rule/…, and picking a theme
in Subject / Topic filters the results.

---

## 8. Building a single-source edition instead

If you only want one source (e.g. State Department alone), the repo also ships
`build_state_cache.py`, which builds `state_events_cache.*` and splices
`state-department-stage.html` from the State adapter only:

```bash
python data/state-department/fetch_state.py
python build_state_cache.py
```

The presidential-only path is the same idea — point a builder at
`data/federal-register/` alone. The combined `build_fr_cache.py` is simply the
two stitched together.

---

## 9. Adapting this for a new agency or document type

The fastest way to make a sibling edition (say, Treasury, or a different agency
slug) is to copy `data/state-department/`, change the `AGENCY` constant in the
new `fetch_*.py` (find the slug at `federalregister.gov/agencies/<slug>`), point
a builder at the new directory, and add a `SOURCE_META` entry + badge to the
HTML. Everything else — the data contract, the themed taxonomy, the doc-type
filter, the splice — is reused unchanged.
```
