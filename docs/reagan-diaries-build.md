# Building the Reagan Diaries Records Stage instance (CLI)

`build_reagan_stage.py` turns Ronald Reagan's personal presidential diary into
**`reagan-diaries-stage.html`** — the standard Records Stage publishing tool
(preset campaign builder, clearance editor, Word export, the NARA + Wikimedia
Commons + Library of Congress image modal) carrying the diary as its corpus.

For the click-through equivalent through the Records Studio wizard, see
[`reagan-diaries-records-studio.md`](reagan-diaries-records-studio.md). Both
paths produce the same artifact.

---

## The corpus

A single XML file: a 2013 transcription of the Reagan Foundation's per-day XML
editions of *the personal diary* (published as *The Reagan Diaries*, ed. Douglas
Brinkley). It is **not** the White House "Daily Diary" activity logbook held at
reaganlibrary.gov — that is a different record.

Shape:

```xml
<diary>
  <entry date="1981-01-20">
    <head><source-url>…</source-url>…</head>
    <body><p>The Inaugural (Jan. 20) was an emotional experience…</p></body>
  </entry>
  …
</diary>
```

2,500 entries, one per real calendar date, spanning **1981-01-20 → 1989-01-20**.

Place it at (everything under `data/` is gitignored — the file is
re-obtainable and not ours to redistribute):

```
data/reagan-diaries/diary.xml
```

---

## Build

```bash
python build_reagan_stage.py
```

Output:

```
  events: 2500
  skipped_bad_or_empty: 0
  days_with_events: 366        # 366 = Feb 29 present (1984, 1988)
  year_range: 1981–1989
  ✓ reagan-diaries-stage.html written (3.6 MB)
```

The script parses the XML, buckets entries by `MM-DD`, writes
`reagan_events_cache.{json,js}`, then starts from a fresh copy of the vendored
`records-stage.html` shell, retitles it **"The Reagan Diaries — Records Stage"**,
and splices the cache in via `html_embed.sync_html_embed`. Publish the
`reagan-diaries-stage.html` it produces.

`--no-html-sync` builds the caches only; `--html`, `--json-out`, `--js-out`
override the output paths.

---

## How the diary maps into the event contract

| Contract field | Value | Notes |
|---|---|---|
| `source` | `"The Reagan Diaries"` | One homogeneous corpus → **one** source-filter chip (unlike Founders' 7 editions). |
| `year` / `month` / `day` | from the `date` attr | Zero-padded `MM`/`DD` so the bucket key matches the shell's lookup. One entry per date, so "Browse by Date / On This Day" surfaces every year sharing an `MM-DD` (e.g. **Jan 20 → 1981 *and* 1989**). |
| `title` | the **full entry text** | All `<p>` paragraphs joined, whitespace normalized. See the design note below. |
| `url` | `…/diary-entry-MMDDYYYY` | Per-entry deep link, reconstructed. See the URL note below. |

No score (the shell only badges / min-score-filters FRUS) and no subjects (the
diary carries none), so each compact event is just `{y,t,u,s}` and
`SUBJECT_TAXONOMY` is emitted empty — the topic filter stays inert, exactly like
the Founders and Federal Register instances.

### Design note — why the full entry text goes in `title`

In this shell, `title` is triple-duty: it is what each row displays, it is the
**only** field full-text search scans, and it is what the **AI drafter feeds to
Claude**. There is no separate "body" field wired into search or drafting. The
diary's whole value is the entry prose, so the parser puts the full,
whitespace-normalized entry text in `title`. Trade-off: list rows are taller
than a one-line headline — which, for a diary you actually want to *read*, is the
right call. (Paragraph breaks don't survive — the shell renders `title` in one
wrapping div — so paragraphs are joined by a single space.)

### URL note — the original links are dead

The scraped `source-url`s (`reaganfoundation.org/xml/MM-DD-YYYY.xml`) now all
**404**. The Foundation republished the diary at readable per-entry pages with a
predictable stem, so the builder reconstructs each entry's URL as:

```
https://www.reaganfoundation.org/ronald-reagan/white-house-diaries/diary-entry-MMDDYYYY
```

A spot-check across the run resolves **~96%** of these; a small remainder (entries
the Foundation didn't publish a page for) will 404. That is strictly better than
the uniformly-dead XML links and no worse than a single static landing page for
the entries that do resolve. The collection home, if you want a fallback link, is
<https://www.reaganfoundation.org/ronald-reagan/white-house-diaries>.

---

## Data caveats

- **Search is entry-text-only.** There are no subject tags or separate metadata
  fields — search matches the diary prose itself (which is usually what you want).
- **Reagan's shorthand is preserved verbatim** — abbreviations ("ec. plan",
  "N.S.C.", "V.P."), curly quotes, and em-dashes come through as written. Keep
  this in mind when searching (search "Secretary" and you'll miss "Sec'y").
- **Not every calendar day has an entry**, and a few days carry only some of the
  eight years — Reagan didn't write daily. `366` day-buckets includes Feb 29.
- **~4% of deep links 404** (see the URL note above).

---

## Rebuilding

The instance is fully regenerable — delete `reagan-diaries-stage.html` and the
two `reagan_events_cache.*` files and re-run `python build_reagan_stage.py`. The
build always starts from the current vendored `records-stage.html`, so any fix
already in that shell (model id for AI drafts, image-modal changes, etc.) is
inherited for free on the next build.
